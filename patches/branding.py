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

    new = old + """
            const SizedBox(height: 8.0),
            TextButton(
              onPressed: () {
                launchUrlString('https://relay.azatmutq.com/_admin/#/register');
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
    print("=== branding patches done ===")


if __name__ == "__main__":
    main()
