import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import threading
import urllib.request
import zipfile
from pathlib import Path

from ..config import settings

_GRADLE_VERSION = "9.5.0"
_GRADLE_URL = f"https://services.gradle.org/distributions/gradle-{_GRADLE_VERSION}-bin.zip"
_ANDROID_TOOLS_VERSION = "15859902"
_ANDROID_TOOLS_URL = f"https://dl.google.com/android/repository/commandlinetools-linux-{_ANDROID_TOOLS_VERSION}_latest.zip"
_ADOPTIUM_JDK_URL = (
    "https://api.adoptium.net/v3/binary/latest/17/ga/linux/x64/jdk/hotspot/normal/eclipse"
)

BUILD_ROOT = settings.generated / "_build"
TOOLCHAIN_ROOT = settings.generated / ".toolchain"
SDK_ROOT = TOOLCHAIN_ROOT / "android-sdk"
GRADLE_ROOT = TOOLCHAIN_ROOT / f"gradle-{_GRADLE_VERSION}"
JDK_ROOT = TOOLCHAIN_ROOT / "jdk-17"
WORKSPACE = BUILD_ROOT / "workspace"
TOOLCHAIN_READY = TOOLCHAIN_ROOT / ".ready"
GRADLE_READY = TOOLCHAIN_ROOT / ".gradle-ready"

_lock = threading.Lock()


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(destination.suffix + ".part")
    if tmp.exists():
        tmp.unlink()
    request = urllib.request.Request(url, headers={"User-Agent": "Android-GPT/4.0"})
    with urllib.request.urlopen(request, timeout=120) as response, tmp.open("wb") as out:
        while True:
            chunk = response.read(4 * 1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
    tmp.replace(destination)


def _run(
    command: list[str],
    cwd: Path | None = None,
    env: dict | None = None,
    input_text: str | None = None,
    timeout: int = 900,
) -> str:
    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        env=env,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Comando falhou ({result.returncode}): {' '.join(command)}\n{result.stdout[-12000:]}"
        )
    return result.stdout


def _java_home() -> Path:
    system_java = shutil.which("java")
    if system_java:
        try:
            out = _run([system_java, "-version"], timeout=20)
            if re.search(r'version "(?:1\.)?(?:17|18|19|20|21|22|23|24|25)', out):
                return Path(system_java).resolve().parent.parent
        except Exception:
            pass

    java_bin = JDK_ROOT / "bin" / "java"
    if not java_bin.exists():
        archive = TOOLCHAIN_ROOT / "jdk17.tar.gz"
        _download(_ADOPTIUM_JDK_URL, archive)
        JDK_ROOT.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive, "r:gz") as tar:
            members = tar.getmembers()
            top = members[0].name.split("/", 1)[0]
            for member in members:
                if member.name == top or member.name.startswith(top + "/"):
                    member.name = member.name[len(top):].lstrip("/")
                    if member.name:
                        tar.extract(member, JDK_ROOT)
        archive.unlink(missing_ok=True)
    if not java_bin.exists():
        raise RuntimeError("Não foi possível obter um JDK 17 para compilar o APK.")
    return JDK_ROOT


def _gradle_bin() -> Path:
    candidate = GRADLE_ROOT / "bin" / "gradle"
    if candidate.exists():
        return candidate
    archive = TOOLCHAIN_ROOT / f"gradle-{_GRADLE_VERSION}-bin.zip"
    _download(_GRADLE_URL, archive)
    TOOLCHAIN_ROOT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(TOOLCHAIN_ROOT)
    archive.unlink(missing_ok=True)
    if not candidate.exists():
        raise RuntimeError("Gradle não foi instalado corretamente.")
    candidate.chmod(candidate.stat().st_mode | 0o111)
    return candidate


def _sdkmanager() -> Path:
    candidate = SDK_ROOT / "cmdline-tools" / "latest" / "bin" / "sdkmanager"
    if candidate.exists():
        return candidate
    archive = TOOLCHAIN_ROOT / "commandlinetools.zip"
    _download(_ANDROID_TOOLS_URL, archive)
    temp = TOOLCHAIN_ROOT / "cmdline-tools-extract"
    if temp.exists():
        shutil.rmtree(temp)
    temp.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(temp)
    source = temp / "cmdline-tools"
    target = SDK_ROOT / "cmdline-tools" / "latest"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.rmtree(target)
    shutil.move(str(source), str(target))
    shutil.rmtree(temp, ignore_errors=True)
    archive.unlink(missing_ok=True)
    if not candidate.exists():
        raise RuntimeError("Android command-line tools não foram instaladas corretamente.")
    candidate.chmod(candidate.stat().st_mode | 0o111)
    return candidate


def _ensure_sdk(java_home: Path) -> Path:
    sdkmanager = _sdkmanager()
    env = os.environ.copy()
    env["ANDROID_HOME"] = str(SDK_ROOT)
    env["ANDROID_SDK_ROOT"] = str(SDK_ROOT)
    env["JAVA_HOME"] = str(java_home)

    platform = SDK_ROOT / "platforms" / "android-36"
    build_tools = SDK_ROOT / "build-tools" / "36.0.0"
    license_marker = SDK_ROOT / ".licenses_accepted"

    if not license_marker.exists():
        _run(
            [str(sdkmanager), "--sdk_root=" + str(SDK_ROOT), "--licenses"],
            env=env,
            input_text="y\n" * 40,
            timeout=300,
        )
        license_marker.touch()

    missing: list[str] = []
    if not platform.exists():
        missing.append("platforms;android-36")
    if not build_tools.exists():
        missing.append("build-tools;36.0.0")
    if missing:
        _run(
            [str(sdkmanager), "--sdk_root=" + str(SDK_ROOT), *missing],
            env=env,
            timeout=900,
        )

    TOOLCHAIN_READY.touch()
    return SDK_ROOT


def _safe_slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    value = value.strip("._-")
    return (value or "android_gpt_agent")[:48]


def _build_key(app_name: str, server_url: str, features: dict[str, bool]) -> str:
    payload = {
        "app_name": app_name,
        "server_url": server_url.rstrip("/"),
        "features": features,
        "builder": 4,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()[:20]


def _escaped_java_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")


def write_android_project(project: Path, app_name: str, server_url: str, features: dict[str, bool]) -> None:
    package_name = "com.jolgue.androidgptagent"
    src = project / "app" / "src" / "main"
    java_dir = src / "java" / Path(*package_name.split("."))
    java_dir.mkdir(parents=True, exist_ok=True)

    safe_app_name = (
        app_name.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
    strings = f'''<resources>\n    <string name="app_name">{safe_app_name}</string>\n</resources>\n'''

    manifest = '''<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.INTERNET" />
    <application android:theme="@style/AppTheme" android:label="@string/app_name" android:usesCleartextTraffic="true" android:allowBackup="false" android:supportsRtl="true">
        <activity android:name=".MainActivity" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
'''

    values_dir = src / "res" / "values"
    values_dir.mkdir(parents=True, exist_ok=True)
    styles = '''<resources>
    <style name="AppTheme" parent="android:style/Theme.Material.Light.NoActionBar">
        <item name="android:fontFamily">sans</item>
        <item name="android:colorAccent">#6750A4</item>
    </style>
</resources>
'''

    endpoint = server_url.rstrip("/") + "/api/devices/register"
    heartbeat = server_url.rstrip("/") + "/api/devices/{device_id}/heartbeat"
    title = _escaped_java_string(app_name)
    java = f'''package {package_name};

import android.app.Activity;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.UUID;

public class MainActivity extends Activity {{
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final String deviceId = UUID.randomUUID().toString();
    private final String registerUrl = "{_escaped_java_string(endpoint)}";
    private final String heartbeatUrl = "{_escaped_java_string(heartbeat)}";
    private TextView status;

    @Override public void onCreate(Bundle state) {{
        super.onCreate(state);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(48, 64, 48, 48);
        layout.setGravity(Gravity.CENTER);
        TextView title = new TextView(this);
        title.setText("{title}");
        title.setTextSize(24);
        status = new TextView(this);
        status.setText("A ligar ao servidor…");
        status.setTextSize(16);
        layout.addView(title);
        layout.addView(status);
        setContentView(layout);
        register();
        handler.postDelayed(new Runnable() {{ @Override public void run() {{ heartbeat(); handler.postDelayed(this, 30000); }} }}, 30000);
    }}

    private String jsonEscape(String s) {{ return s.replace("\\\\", "\\\\\\\\").replace("\"", "\\\\\""); }}

    private void register() {{
        new Thread(() -> {{
            try {{
                String body = "{{\"id\":\"" + jsonEscape(deviceId) + "\",\"name\":\"" + jsonEscape(Build.MANUFACTURER + " " + Build.MODEL) + "\",\"model\":\"" + jsonEscape(Build.MODEL) + "\",\"android_version\":\"" + Build.VERSION.RELEASE + "\"}}";
                post(registerUrl, body);
                runOnUiThread(() -> status.setText("Ligado ao servidor\n" + Build.MANUFACTURER + " " + Build.MODEL));
            }} catch (Exception e) {{ runOnUiThread(() -> status.setText("Erro ao ligar: " + e.getClass().getSimpleName())); }}
        }}).start();
    }}

    private void heartbeat() {{ new Thread(() -> {{ try {{ post(heartbeatUrl.replace("{{device_id}}", deviceId), ""); }} catch (Exception ignored) {{ }} }}).start(); }}

    private void post(String target, String body) throws Exception {{
        HttpURLConnection c = (HttpURLConnection) new URL(target).openConnection();
        c.setRequestMethod("POST");
        c.setConnectTimeout(10000); c.setReadTimeout(10000); c.setDoOutput(true);
        c.setRequestProperty("Content-Type", "application/json");
        try (OutputStream os = c.getOutputStream()) {{ os.write(body.getBytes(StandardCharsets.UTF_8)); }}
        c.getResponseCode(); c.disconnect();
    }}
}}
'''

    (project / "settings.gradle").write_text(
        "pluginManagement { repositories { google(); mavenCentral(); gradlePluginPortal() } }\n"
        "dependencyResolutionManagement { repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS); repositories { google(); mavenCentral() } }\n"
        "rootProject.name = 'AndroidGPTAgent'\ninclude ':app'\n",
        encoding="utf-8",
    )
    (project / "build.gradle").write_text(
        "plugins { id 'com.android.application' version '9.3.0' apply false }\n",
        encoding="utf-8",
    )
    (project / "gradle.properties").write_text(
        "org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8\n"
        "org.gradle.caching=true\n"
        "org.gradle.parallel=true\n"
        "org.gradle.configuration-cache=true\n"
        "org.gradle.daemon=true\n"
        "android.useAndroidX=true\n",
        encoding="utf-8",
    )
    (project / "app" / "build.gradle").write_text(
        """plugins { id 'com.android.application' }\n\nandroid {\n    namespace 'com.jolgue.androidgptagent'\n    compileSdk 36\n    defaultConfig {\n        applicationId 'com.jolgue.androidgptagent'\n        minSdk 23\n        targetSdk 36\n        versionCode 1\n        versionName '1.0'\n    }\n}\n""",
        encoding="utf-8",
    )
    (src / "AndroidManifest.xml").write_text(manifest, encoding="utf-8")
    (src / "res" / "values" / "strings.xml").write_text(strings, encoding="utf-8")
    (src / "res" / "values" / "styles.xml").write_text(styles, encoding="utf-8")
    (java_dir / "MainActivity.java").write_text(java, encoding="utf-8")
    (project / "android-gpt.json").write_text(
        json.dumps({"app_name": app_name, "server_url": server_url, "features": features}, indent=2),
        encoding="utf-8",
    )


def build_apk(app_name: str, server_url: str, features: dict[str, bool]) -> tuple[Path, Path]:
    build_key = _build_key(app_name, server_url, features)
    final_dir = settings.generated / "apks"
    final_dir.mkdir(parents=True, exist_ok=True)
    final_apk = final_dir / f"{_safe_slug(app_name)}-{build_key}.apk"

    # Exact same build: return the existing artifact without invoking Gradle.
    if final_apk.is_file() and final_apk.stat().st_size > 0:
        return final_apk, WORKSPACE

    with _lock:
        if final_apk.is_file() and final_apk.stat().st_size > 0:
            return final_apk, WORKSPACE

        BUILD_ROOT.mkdir(parents=True, exist_ok=True)
        WORKSPACE.mkdir(parents=True, exist_ok=True)

        java_home = _java_home()
        sdk = _ensure_sdk(java_home)
        gradle = _gradle_bin()

        # Reuse one persistent Gradle project instead of deleting/recreating it.
        # This lets Gradle/AGP keep incremental state between APK generations.
        write_android_project(WORKSPACE, app_name, server_url, features)

        env = os.environ.copy()
        env["JAVA_HOME"] = str(java_home)
        env["ANDROID_HOME"] = str(sdk)
        env["ANDROID_SDK_ROOT"] = str(sdk)
        env["GRADLE_USER_HOME"] = str(TOOLCHAIN_ROOT / "gradle-user-home")

        cpu_count = os.cpu_count() or 2
        workers = max(2, min(8, cpu_count))
        command = [
            str(gradle),
            "--daemon",
            "--parallel",
            "--configuration-cache",
            f"--max-workers={workers}",
        ]
        if GRADLE_READY.exists():
            command.append("--offline")
        command.append("assembleDebug")

        _run(command, cwd=WORKSPACE, env=env, timeout=900)

        apk = WORKSPACE / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
        if not apk.exists():
            raise RuntimeError("A compilação terminou sem produzir o APK.")

        # The first successful build proves that Gradle dependencies are cached locally.
        GRADLE_READY.touch()
        shutil.copy2(apk, final_apk)
        return final_apk, WORKSPACE
