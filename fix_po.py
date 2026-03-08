import glob
import os

for po_file in glob.glob('i18n/**/*.po', recursive=True):
    with open(po_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    # Find and extract Verina C2 block
    verina_lines = []
    verina_start = -1
    for i in range(len(lines)):
        if 'msgid "Verina C2"' in lines[i]:
            verina_start = i
            break
            
    if verina_start != -1:
        # Extract msgid and msgstr
        verina_lines.append(lines[verina_start])  # msgid
        verina_lines.append(lines[verina_start+1]) # msgstr
        # Remove them from original position + trailing newline if exists
        del lines[verina_start:verina_start+2]
            
    verina_string = "".join(verina_lines)
    
    # Now find Iuno C6 to insert Verina C2 after its msgstr
    iuno_end = -1
    for i in range(len(lines)):
        if 'msgid "Iuno C6"' in lines[i]:
            iuno_end = i + 1
            break
            
    if iuno_end != -1 and verina_string:
        # Insert a newline, then Verina block, directly after Iuno msgstr
        lines.insert(iuno_end + 1, "\n" + verina_string)
        
    # Clean up any trailing empty lines at the very end of file
    while lines and lines[-1].strip() == "":
        lines.pop()
    lines.append('\n')
        
    with open(po_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)
