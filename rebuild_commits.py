import os
import glob
import subprocess

try:
    import polib
except ImportError:
    subprocess.run("pip install polib", shell=True)
    import polib

def run(cmd):
    print(f"Running: {cmd}")
    subprocess.run(cmd, shell=True, check=True)

try:
    # Save translations from e3e9e99 to memory
    run("git checkout e3e9e99 -- i18n/ config.py")
    verina_translations = {}
    for po_file in glob.glob('i18n/*/LC_MESSAGES/ok.po'):
        po = polib.pofile(po_file)
        for entry in po:
            if entry.msgid == "Verina C2":
                verina_translations[po_file] = entry.msgstr
                break

    # Rebuild process
    run("git reset --hard upstream/master")
    run("git checkout -B feat/verina-combat-logic")

    # Commit 1
    run("git checkout 69bb6ea -- src/char/Verina.py")
    run('git commit -m "feat(combat): 重寫維里奈自動戰鬥邏輯"')

    # Commit 2
    run("git checkout upstream/master -- config.py i18n/")
    # Update config.py
    with open("config.py", "r", encoding="utf-8") as f:
        config_text = f.read()
    config_text = config_text.replace("'Iuno C6': False,\n    'Chisa DPS': False,", "'Iuno C6': False,\n    'Verina C2': False,\n    'Chisa DPS': False,")
    with open("config.py", "w", encoding="utf-8") as f:
        f.write(config_text)

    # Update po files
    for po_file in glob.glob('i18n/*/LC_MESSAGES/ok.po'):
        with open(po_file, "r", encoding="utf-8") as f:
            po_content = f.read()
        
        t = verina_translations.get(po_file, "")
        verina_block = f'msgid "Verina C2"\nmsgstr "{t}"\n\n'
        
        # We need to find the exact replacement location in upstream/master po files
        # Depending on how the msgstrs are, it might not just be msgstr "" if they were translated?
        # WAIT! In upstream/master, they were empty. But let's be safe.
        po = polib.pofile(po_file)
        for entry in po:
            if entry.msgid == "Iuno C6":
                iuno_c6_str = entry.msgstr
            if entry.msgid == "Chisa DPS":
                chisa_dps_str = entry.msgstr
        
        target = f'msgid "Iuno C6"\nmsgstr "{iuno_c6_str}"\n\nmsgid "Chisa DPS"'
        replacement = f'msgid "Iuno C6"\nmsgstr "{iuno_c6_str}"\n\n{verina_block}msgid "Chisa DPS"'
        
        if target in po_content:
            po_content = po_content.replace(target, replacement)
        else:
            print(f"Warning: Could not find target in {po_file}")
            # Fallback append
            po_content += f'\n\n{verina_block.strip()}'
        
        with open(po_file, "w", encoding="utf-8") as f:
            f.write(po_content)
        
        # compile mo
        polib.pofile(po_file).save_as_mofile(po_file.replace(".po", ".mo"))

    run("git add config.py i18n/")
    run('git commit -m "feat(i18n): 加入 Verina C2 維里奈二命設定項的多國語系支援"')

    # Commit 3
    run("git checkout e3e9e99 -- config.py i18n/")
    # Handle trailing newlines user asked for
    for po_file in glob.glob('i18n/*/LC_MESSAGES/ok.po'):
        with open(po_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        while lines and lines[-1].strip() == '':
            lines.pop()
        with open(po_file, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        # compile mo securely
        polib.pofile(po_file).save_as_mofile(po_file.replace(".po", ".mo"))

    run("git add config.py i18n/")
    run('git commit -m "feat(i18n): 修復千咲與尤諾翻譯並整理格式"')

except Exception as e:
    print(f"Error: {e}")

