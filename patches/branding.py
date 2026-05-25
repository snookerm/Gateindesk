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


def patch_remove_update_guard_buildhelpcards():
    """THIRD is_custom_client guard for updates lives in
    desktop_home_page.dart:432-457 buildHelpCards(). Two filters block
    custom-clients from ever seeing the update card:

      if (!bind.isCustomClient() &&
          updateUrl.isNotEmpty &&
          !isCardClosed &&
          bind.mainUriPrefixSync().contains('rustdesk')) {

    Even with Rust + checkUpdate Dart guards removed (so the call
    fires and updateUrl gets populated), this widget refuses to render
    the banner for our fork. Found 2026-05-25 after nginx access log
    confirmed 3 successful POST /api/version/latest with HTTP 200 but
    no banner shown.

    Also rewrites two upstream URLs inside the card:
      - https://rustdesk.com/download  -> https://download.azatmutq.com/gateindesk/
      - https://github.com/rustdesk/rustdesk/releases/tag/X
                                       -> https://github.com/snookerm/Gateindesk/releases
    """
    f = Path("flutter/lib/desktop/pages/desktop_home_page.dart")
    src = f.read_text(encoding="utf-8")
    if "GD_PATCHED_BUILDHELPCARDS" in src:
        print("buildHelpCards guard: skip (already patched)")
        return

    # Remove the two upstream-only filters
    old_guard = (
        "    if (!bind.isCustomClient() &&\n"
        "        updateUrl.isNotEmpty &&\n"
        "        !isCardClosed &&\n"
        "        bind.mainUriPrefixSync().contains('rustdesk')) {"
    )
    new_guard = (
        "    // GD_PATCHED_BUILDHELPCARDS — removed isCustomClient + rustdesk URI checks\n"
        "    if (updateUrl.isNotEmpty && !isCardClosed) {"
    )
    if old_guard not in src:
        print("buildHelpCards guard: skip (guard anchor not found)")
        return
    src = src.replace(old_guard, new_guard, 1)

    # Rewrite upstream URL for the Download branch (fallback when not installed)
    src = src.replace(
        "final Uri url = Uri.parse('https://rustdesk.com/download');",
        "final Uri url = Uri.parse('https://download.azatmutq.com/gateindesk/');",
    )

    # Rewrite changelog link to our repo releases
    src = src.replace(
        "'https://github.com/rustdesk/rustdesk/releases/tag/${bind.mainGetNewVersion()}'",
        "'https://github.com/snookerm/Gateindesk/releases'",
    )

    f.write_text(src, encoding="utf-8")
    print("buildHelpCards guard: removed + URLs rewritten")


def patch_remove_update_guard_dart():
    """RustDesk has TWO is_custom_client guards for update checks:
    one in Rust (common.rs check_software_update — handled by
    patch_remove_update_guard) AND one in Dart (common.dart:3976-3991
    checkUpdate). The Dart one blocks the actual call to
    mainGetSoftwareUpdateUrl, so even with Rust patched the function
    never fires. Found 2026-05-25 after empirical test on user machine
    showed 0 TCP connections to api.azatmutq.com.
    """
    f = Path("flutter/lib/common.dart")
    src = f.read_text(encoding="utf-8")
    needle = (
        "void checkUpdate() {\n"
        "  if (!isWeb) {\n"
        "    if (!bind.isCustomClient()) {\n"
    )
    if needle not in src:
        if "if (!isWeb) {\n    platformFFI.registerEventHandler" in src:
            print("update guard (Dart): skip (already removed)")
        else:
            print("update guard (Dart): skip (anchor not found)")
        return
    # Replace: drop the inner `if (!bind.isCustomClient()) {` and its closing brace.
    # Original:
    #   if (!isWeb) {
    #     if (!bind.isCustomClient()) {
    #       platformFFI.registerEventHandler(...);
    #       Timer(...);
    #     }
    #   }
    # Patched:
    #   if (!isWeb) {
    #     platformFFI.registerEventHandler(...);
    #     Timer(...);
    #   }
    old_block = (
        "void checkUpdate() {\n"
        "  if (!isWeb) {\n"
        "    if (!bind.isCustomClient()) {\n"
        "      platformFFI.registerEventHandler(\n"
        "          kCheckSoftwareUpdateFinish, kCheckSoftwareUpdateFinish,\n"
        "          (Map<String, dynamic> evt) async {\n"
        "        if (evt['url'] is String) {\n"
        "          stateGlobal.updateUrl.value = evt['url'];\n"
        "        }\n"
        "      });\n"
        "      Timer(const Duration(seconds: 1), () async {\n"
        "        bind.mainGetSoftwareUpdateUrl();\n"
        "      });\n"
        "    }\n"
        "  }\n"
        "}\n"
    )
    new_block = (
        "void checkUpdate() {\n"
        "  if (!isWeb) {\n"
        "    platformFFI.registerEventHandler(\n"
        "        kCheckSoftwareUpdateFinish, kCheckSoftwareUpdateFinish,\n"
        "        (Map<String, dynamic> evt) async {\n"
        "      if (evt['url'] is String) {\n"
        "        stateGlobal.updateUrl.value = evt['url'];\n"
        "      }\n"
        "    });\n"
        "    Timer(const Duration(seconds: 1), () async {\n"
        "      bind.mainGetSoftwareUpdateUrl();\n"
        "    });\n"
        "  }\n"
        "}\n"
    )
    if old_block not in src:
        print("update guard (Dart): skip (block anchor not found — upstream changed?)")
        return
    src = src.replace(old_block, new_block, 1)
    f.write_text(src, encoding="utf-8")
    print("update guard (Dart): isCustomClient block removed")


def patch_remove_update_guard():
    """Remove `if is_custom_client() { return; }` guard at the top of
    check_software_update so OUR fork actually polls /api/version/latest.

    The original guard is multi-line — sed in workflow can't match across
    newlines reliably, so this Python patch does it.
    """
    f = Path("src/common.rs")
    src = f.read_text(encoding="utf-8")
    needle = (
        "pub fn check_software_update() {\n"
        "    if is_custom_client() {\n"
        "        return;\n"
        "    }\n"
    )
    if needle not in src:
        if "pub fn check_software_update() {\n    let opt" in src:
            print("update guard: skip (already removed)")
        else:
            print("update guard: skip (anchor not found — upstream changed?)")
        return
    replacement = "pub fn check_software_update() {\n"
    src = src.replace(needle, replacement, 1)
    f.write_text(src, encoding="utf-8")
    print("update guard: is_custom_client early-return removed")


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


def patch_support_dialog():
    """Inject the support dialog implementation into common.dart so it can
    be invoked from anywhere (sidebar, About, etc).

    Sidebar link is added separately by patch_support_link_in_sidebar.
    No link in About — user wants it under update banner in sidebar.
    """
    f = Path("flutter/lib/common.dart")
    src = f.read_text(encoding="utf-8")
    if "showGateInDeskSupportDialog" in src:
        print("support dialog: skip (already injected in common.dart)")
        return

    # Ensure http_service import is present (already used elsewhere via 'http')
    if "as gd_http;" not in src:
        first_import = src.find("import ")
        src = src[:first_import] + (
            "import 'utils/http_service.dart' as gd_http;\n"
        ) + src[first_import:]

    # Ensure dart:io and url_launcher are imported (for File/Platform/launchUrl).
    # common.dart already imports url_launcher but check; dart:io may or may not be.
    if "import 'dart:io'" not in src:
        first_import = src.find("import ")
        src = src[:first_import] + "import 'dart:io';\n" + src[first_import:]
    if "package:url_launcher/url_launcher.dart" not in src:
        first_import = src.find("import ")
        src = src[:first_import] + "import 'package:url_launcher/url_launcher.dart';\n" + src[first_import:]

    helper = '''

// ────────────────────────────────────────────────────────────────────
// GateInDesk support form (added by patches/branding.py)
// POST https://api.azatmutq.com/api/support → SMTP to gurgen@gateinweb.ru
// Optional attached logs (text concat, base64) up to ~3 MB.
// ────────────────────────────────────────────────────────────────────

// Collect last N rotated GateInDesk_r*.log files from %APPDATA%/GateInDesk/log
// (or platform-equivalent), concat with file headers, cap total size to 3 MB.
// Returns null if nothing found or error.
String? _collectGateInDeskLogs() {
  try {
    final appData = Platform.environment['APPDATA']
        ?? Platform.environment['HOME']
        ?? '';
    if (appData.isEmpty) return null;
    final logDir = Directory('\\$appData\\\\GateInDesk\\\\log');
    if (!logDir.existsSync()) return null;

    // Pick last 5 log files by modification time (newest first).
    final files = logDir
        .listSync()
        .whereType<File>()
        .where((f) => f.path.toLowerCase().endsWith('.log'))
        .toList()
      ..sort((a, b) => b.statSync().modified.compareTo(a.statSync().modified));
    final picked = files.take(5).toList();
    if (picked.isEmpty) return null;

    final buf = StringBuffer();
    const int maxBytes = 3 * 1024 * 1024;  // 3 MB cap before base64
    for (final f in picked) {
      if (buf.length >= maxBytes) break;
      try {
        final name = f.path.split(Platform.pathSeparator).last;
        buf.writeln('=== FILE: \\$name (\\${f.statSync().size} bytes, mod \\${f.statSync().modified.toIso8601String()}) ===');
        final content = f.readAsStringSync();
        final remaining = maxBytes - buf.length;
        if (content.length > remaining) {
          buf.writeln('[truncated to \\$remaining bytes]');
          buf.write(content.substring(0, remaining));
        } else {
          buf.write(content);
        }
        buf.writeln('\\n');
      } catch (_) {
        // skip unreadable
      }
    }
    return buf.toString();
  } catch (e) {
    debugPrint('_collectGateInDeskLogs failed: \\$e');
    return null;
  }
}

void showGateInDeskSupportDialog(BuildContext context) {
  final nameCtl    = TextEditingController();
  final emailCtl   = TextEditingController();
  final phoneCtl   = TextEditingController();
  final messageCtl = TextEditingController();
  bool sending = false;
  bool attachLogs = true;  // default on — diagnostic value usually wanted
  String? status;
  bool isError = false;

  gFFI.dialogManager.show<bool>((setState, close, context) {
    Future<void> submit() async {
      if (nameCtl.text.trim().isEmpty ||
          emailCtl.text.trim().isEmpty ||
          messageCtl.text.trim().isEmpty) {
        setState(() {
          status = "Заполните ФИО, Email и текст сообщения";
          isError = true;
        });
        return;
      }
      setState(() { sending = true; status = null; isError = false; });
      try {
        final body = <String, dynamic>{
          'name': nameCtl.text.trim(),
          'email': emailCtl.text.trim(),
          'phone': phoneCtl.text.trim(),
          'message': messageCtl.text.trim(),
        };
        if (attachLogs) {
          final logs = _collectGateInDeskLogs();
          if (logs != null && logs.isNotEmpty) {
            body['logs_text_b64'] = base64Encode(utf8.encode(logs));
          }
        }
        final resp = await gd_http.post(
          Uri.parse('https://api.azatmutq.com/api/support'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode(body),
        );
        if (resp.statusCode == 200) {
          setState(() {
            sending = false;
            status = "Сообщение отправлено. Мы свяжемся в течение суток.";
            isError = false;
          });
          Future.delayed(const Duration(seconds: 2), () => close(true));
        } else {
          setState(() {
            sending = false;
            status = "Ошибка сервера: \\${resp.statusCode}";
            isError = true;
          });
        }
      } catch (e) {
        setState(() {
          sending = false;
          status = "Сетевая ошибка. Попробуйте позже.";
          isError = true;
        });
      }
    }

    return CustomAlertDialog(
      title: Text("Служба поддержки GateInDesk"),
      contentBoxConstraints: BoxConstraints(minWidth: 380, maxWidth: 460),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          TextField(controller: nameCtl, decoration: InputDecoration(labelText: "ФИО *")),
          const SizedBox(height: 8),
          TextField(controller: emailCtl, decoration: InputDecoration(labelText: "Email *")),
          const SizedBox(height: 8),
          TextField(controller: phoneCtl, decoration: InputDecoration(labelText: "Телефон")),
          const SizedBox(height: 8),
          TextField(
            controller: messageCtl,
            decoration: InputDecoration(labelText: "Сообщение *"),
            maxLines: 5,
            minLines: 3,
          ),
          const SizedBox(height: 8),
          // Attach-logs checkbox (default ON)
          InkWell(
            onTap: () => setState(() => attachLogs = !attachLogs),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(
                children: [
                  Checkbox(
                    value: attachLogs,
                    onChanged: (v) => setState(() => attachLogs = v ?? false),
                  ),
                  const Expanded(
                    child: Text(
                      "Приложить логи приложения (последние ~3 MB)",
                      style: TextStyle(fontSize: 13),
                    ),
                  ),
                ],
              ),
            ),
          ),
          // Visit-our-site link
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton.icon(
              style: TextButton.styleFrom(padding: EdgeInsets.zero, minimumSize: Size.zero, tapTargetSize: MaterialTapTargetSize.shrinkWrap),
              onPressed: () => launchUrl(
                Uri.parse('https://gateindesk.azatmutq.com'),
                mode: LaunchMode.externalApplication,
              ),
              icon: const Icon(Icons.open_in_new, size: 14),
              label: const Text('Перейти на сайт', style: TextStyle(fontSize: 13)),
            ),
          ),
          if (status != null)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(status!,
                style: TextStyle(
                  color: isError ? Colors.red : Colors.green,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
          if (sending) const Padding(
            padding: EdgeInsets.only(top: 8),
            child: LinearProgressIndicator(),
          ),
        ],
      ),
      onCancel: () => close(false),
      actions: [
        dialogButton("Отмена", onPressed: () => close(false), isOutline: true),
        dialogButton("Отправить", onPressed: sending ? null : submit),
      ],
    );
  });
}
'''
    if not src.rstrip().endswith("}"):
        src += "\n"
    src += helper

    f.write_text(src, encoding="utf-8")
    print("support dialog: implementation injected in common.dart")


def patch_telegram_link_below_powered():
    """Add 'Поддержка в Telegram' link directly under loadPowered hint.
    Opens https://t.me/snookerm926 in external browser/app.
    Separate from the form-based Support card — direct chat in TG.
    """
    f = Path("flutter/lib/desktop/pages/desktop_home_page.dart")
    src = f.read_text(encoding="utf-8")
    if "Поддержка в Telegram" in src:
        print("Telegram link: skip (already injected)")
        return

    # Need url_launcher for launchUrl call
    if "package:url_launcher/url_launcher.dart" not in src:
        first_import = src.find("import ")
        src = src[:first_import] + (
            "import 'package:url_launcher/url_launcher.dart';\n"
        ) + src[first_import:]

    anchor = """      if (bind.isCustomClient())
        Align(
          alignment: Alignment.center,
          child: loadPowered(context),
        ),"""
    if anchor not in src:
        print("Telegram link: skip (loadPowered anchor not found)")
        return

    inject = anchor + """
      // Direct support chat in Telegram (different from the form-based
      // Support card below — instant chat for quick questions).
      if (bind.isCustomClient())
        Align(
          alignment: Alignment.center,
          child: Padding(
            padding: const EdgeInsets.only(top: 2, bottom: 4),
            child: InkWell(
              onTap: () => launchUrl(
                Uri.parse('https://t.me/snookerm926'),
                mode: LaunchMode.externalApplication,
              ),
              child: Text(
                'Поддержка в Telegram',
                style: TextStyle(
                  fontSize: 11,
                  decoration: TextDecoration.underline,
                  color: Color(0xFF0071FF),
                ),
              ),
            ),
          ),
        ),"""

    src = src.replace(anchor, inject)
    f.write_text(src, encoding="utf-8")
    print("Telegram link: injected under loadPowered")


def patch_support_link_in_about():
    """Restore 'Служба поддержки' link inside the About dialog.
    Was removed during the sidebar prominent-card refactor — user
    wants both: prominent card in sidebar AND link in About + TG.
    """
    f = Path("flutter/lib/desktop/pages/desktop_setting_page.dart")
    src = f.read_text(encoding="utf-8")
    if "showGateInDeskSupportDialog" in src:
        print("About Support link: skip (already present)")
        return

    # Anchor: Website InkWell (after our 'Личный кабинет' insert by patch_about_dialog).
    anchor = """InkWell(
                  onTap: () {
                    launchUrlString('https://gateindesk.azatmutq.com');
                  },
                  child: Text(
                    translate('Website'),"""
    if anchor not in src:
        print("About Support link: skip (Website anchor not found)")
        return

    support_link = """InkWell(
                  onTap: () => showGateInDeskSupportDialog(context),
                  child: Text(
                    'Служба поддержки',
                    style: linkStyle,
                  ).marginSymmetric(vertical: 4.0)),
              """ + anchor
    src = src.replace(anchor, support_link)
    f.write_text(src, encoding="utf-8")
    print("About Support link: restored before Website")


def patch_support_link_in_sidebar():
    """Insert a prominent 'Служба поддержки' button card in the desktop
    home left pane, right after the built-in buildHelpCards (which renders
    the update banner). The Support card uses the same visual style as
    Material card buttons — icon + text, full-width, easy to spot.
    """
    f = Path("flutter/lib/desktop/pages/desktop_home_page.dart")
    src = f.read_text(encoding="utf-8")
    if "showGateInDeskSupportDialog" in src:
        print("sidebar Support: skip (already injected)")
        return

    # Anchor: end of buildHelpCards FutureBuilder block + start of buildPluginEntry.
    # Inject our Support card between them.
    anchor = """      FutureBuilder<Widget>(
        future: Future.value(
            Obx(() => buildHelpCards(stateGlobal.updateUrl.value))),
        builder: (_, data) {
          if (data.hasData) {
            if (isIncomingOnly) {
              if (isInHomePage()) {
                Future.delayed(Duration(milliseconds: 300), () {
                  _updateWindowSize();
                });
              }
            }
            return data.data!;
          } else {
            return const Offstage();
          }
        },
      ),
      buildPluginEntry(),"""

    if anchor not in src:
        print("sidebar Support: skip (buildHelpCards anchor not found)")
        return

    # Prominent Support card — Material card style, full-width, icon+text.
    # Sits between update banner and plugin entry → always visible.
    support_card = """      FutureBuilder<Widget>(
        future: Future.value(
            Obx(() => buildHelpCards(stateGlobal.updateUrl.value))),
        builder: (_, data) {
          if (data.hasData) {
            if (isIncomingOnly) {
              if (isInHomePage()) {
                Future.delayed(Duration(milliseconds: 300), () {
                  _updateWindowSize();
                });
              }
            }
            return data.data!;
          } else {
            return const Offstage();
          }
        },
      ),
      // GateInDesk support card — always visible, opens form dialog.
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Material(
          color: Color(0xFFEFF4FF),
          borderRadius: BorderRadius.circular(8),
          child: InkWell(
            borderRadius: BorderRadius.circular(8),
            onTap: () => showGateInDeskSupportDialog(context),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.support_agent, color: Color(0xFF0071FF), size: 20),
                  const SizedBox(width: 8),
                  Text(
                    'Служба поддержки',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                      color: Color(0xFF0071FF),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
      buildPluginEntry(),"""

    src = src.replace(anchor, support_card)
    f.write_text(src, encoding="utf-8")
    print("sidebar Support: prominent card injected below update banner")


def main():
    if not Path("flutter").is_dir():
        sys.exit("error: run from rustdesk/ root (no flutter/ dir here)")
    patch_about_dialog()
    patch_user_model_oidc()
    patch_login_register_button()
    patch_remove_update_guard()
    patch_remove_update_guard_dart()
    patch_remove_update_guard_buildhelpcards()
    patch_main_window_icon()
    patch_support_dialog()
    patch_telegram_link_below_powered()
    patch_support_link_in_sidebar()
    patch_support_link_in_about()
    print("=== branding patches done ===")


if __name__ == "__main__":
    main()
