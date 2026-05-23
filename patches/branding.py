#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GateInDesk branding patches that don't fit into one-line sed.

Run from inside rustdesk/ checkout root (not res/, not flutter/).
All patches are idempotent: repeat invocations are safe.
"""
import sys
from pathlib import Path

# Windows Python defaults to cp1252 for stdout. Force UTF-8 so log lines
# survive (file writes already pin encoding='utf-8' explicitly).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def patch_about_dialog():
    """Insert 'Личный кабинет' InkWell before the Website InkWell in About."""
    f = Path("flutter/lib/desktop/pages/desktop_setting_page.dart")
    src = f.read_text(encoding="utf-8")
    if "'Личный кабинет'" in src:
        print("About: skip (already has account link)")
        return

    website_anchor = """InkWell(
                  onTap: () {
                    launchUrlString('https://relay.azatmutq.com');
                  },
                  child: Text(
                    translate('Website'),"""

    if website_anchor not in src:
        print("About: skip (Website anchor not found)")
        return

    account_link = """InkWell(
                  onTap: () {
                    launchUrlString('https://relay.azatmutq.com/_admin');
                  },
                  child: Text(
                    'Личный кабинет',
                    style: linkStyle,
                  ).marginSymmetric(vertical: 4.0)),
              """ + website_anchor

    f.write_text(src.replace(website_anchor, account_link), encoding="utf-8")
    print("About: account link inserted")


def patch_user_model_oidc():
    """Guard against jsonDecode('null') returning None in queryOidcLoginOptions."""
    f = Path("flutter/lib/models/user_model.dart")
    src = f.read_text(encoding="utf-8")
    old = "return jsonDecode(item.substring('common-oidc/'.length));"
    new = (
        "final decoded = jsonDecode(item.substring('common-oidc/'.length)); "
        "return decoded is List ? decoded : [];"
    )
    if old not in src:
        print("user_model.dart: skip (anchor not found / already patched)")
        return
    f.write_text(src.replace(old, new), encoding="utf-8")
    print("user_model.dart: common-oidc/null guard added")


def patch_main_window_icon():
    """Force-set window icon via window_manager using ABSOLUTE path.

    window_manager.cpp SetIcon uses LoadImage(NULL, path, ..., LR_LOADFROMFILE)
    which resolves relative paths against the process CWD, not the exe dir.
    When started from Start Menu / desktop shortcut on Windows, CWD is often
    C:\\Windows\\System32 -> relative 'assets/icon.ico' fails -> LoadImage
    returns NULL -> SetIcon sends NULL handle -> Windows shows default icon.
    Some shortcuts set 'Start In' correctly, hence works on one machine and
    not on another (incident 2026-05-24).

    Fix: build absolute path from Platform.resolvedExecutable.
    """
    f = Path("flutter/lib/main.dart")
    src = f.read_text(encoding="utf-8")

    # Idempotency: drop any earlier (broken) relative setIcon line
    bad = "windowManager.setIcon('assets/icon.ico');\n    "
    if bad in src:
        src = src.replace(bad, "")

    if "_setGateInDeskWindowIcon" in src:
        print("main.dart: skip (already has _setGateInDeskWindowIcon)")
        f.write_text(src, encoding="utf-8")
        return

    anchor = "windowManager.setTitle(getWindowName());"
    if anchor not in src:
        print("main.dart: skip (setTitle anchor not found)")
        return

    call = ("_setGateInDeskWindowIcon();\n"
            "    windowManager.setTitle(getWindowName());")
    src = src.replace(anchor, call)

    helper = (
        "\n"
        "// Set window icon via absolute path (window_manager LoadImage requires\n"
        "// LR_LOADFROMFILE to resolve from process CWD which is unreliable when\n"
        "// app is launched from Start Menu/shortcut). Built from exe dir.\n"
        "void _setGateInDeskWindowIcon() {\n"
        "  try {\n"
        "    final exeDir = File(Platform.resolvedExecutable).parent.path;\n"
        "    final ico = '\\$exeDir\\\\data\\\\flutter_assets\\\\assets\\\\icon.ico';\n"
        "    if (File(ico).existsSync()) {\n"
        "      windowManager.setIcon(ico);\n"
        "    }\n"
        "  } catch (e) {\n"
        "    debugPrint('setIcon failed: \\$e');\n"
        "  }\n"
        "}\n"
    )

    # Append helper at end of file (top-level function)
    if not src.rstrip().endswith("}"):
        src = src + "\n"
    src = src + helper

    # Ensure dart:io is imported
    if "import 'dart:io'" not in src:
        # Insert after first import line
        import_line = "import 'dart:io';\n"
        first_import = src.find("import ")
        if first_import != -1:
            src = src[:first_import] + import_line + src[first_import:]

    f.write_text(src, encoding="utf-8")
    print("main.dart: _setGateInDeskWindowIcon helper injected (absolute path)")


def patch_login_register_button():
    """Add Регистрация TextButton under the Login button in user/pass login form."""
    f = Path("flutter/lib/common/widgets/login.dart")
    src = f.read_text(encoding="utf-8")
    if "'Регистрация'" in src:
        print("login.dart: skip (already has register button)")
        return

    # Anchor: the FittedBox row that wraps the Login ElevatedButton.
    # We append a Register TextButton after its closing brackets.
    old = """            FittedBox(
                child:
                    Row(mainAxisAlignment: MainAxisAlignment.center, children: [
              Container(
                height: 38,
                width: 200,
                child: Obx(() => ElevatedButton(
                      child: Text(
                        translate('Login'),
                        style: TextStyle(fontSize: 16),
                      ),
                      onPressed:
                          curOP.value.isEmpty || curOP.value == 'rustdesk'
                              ? () {
                                  onLogin();
                                }
                              : null,
                    )),
              ),
            ])),"""

    if old not in src:
        print("login.dart: skip (Login button anchor not found)")
        return

    # login.dart imports only `package:url_launcher/url_launcher.dart`
    # (NOT url_launcher_string). Use launchUrl(Uri.parse(...)) — same as line 175.
    new = old + """
            const SizedBox(height: 8.0),
            TextButton(
              onPressed: () {
                launchUrl(Uri.parse('https://relay.azatmutq.com/_admin/#/register'),
                    mode: LaunchMode.externalApplication);
              },
              child: Text('Регистрация', style: TextStyle(fontSize: 14)),
            ),"""

    f.write_text(src.replace(old, new), encoding="utf-8")
    print("login.dart: register button inserted")


def main():
    if not Path("flutter").is_dir():
        sys.exit("error: run from rustdesk/ root (no flutter/ dir here)")
    patch_about_dialog()
    patch_user_model_oidc()
    patch_login_register_button()
    patch_main_window_icon()
    print("=== branding patches done ===")


if __name__ == "__main__":
    main()
