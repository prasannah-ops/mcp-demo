#run with python3 -c
import os, shutil
os.system('curl -L https://github.com/taylorwilsdon/google_workspace_mcp/archive/refs/heads/main.zip -o repo.zip')
os.system('unzip -q repo.zip')
base = 'google_workspace_mcp-main'
folders = ['auth', 'core', 'gmail', 'gcalendar']
for f in folders:
    if os.path.exists(f): shutil.rmtree(f)
    shutil.move(f'{base}/{f}', f)
os.system('rm -rf google_workspace_mcp-main repo.zip')
print('✅ Gmail, Calendar, Auth, and Core files successfully copied!')
