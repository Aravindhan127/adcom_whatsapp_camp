import os, glob, re

files = [
    'app/routes/template_routes.py',
    'app/routes/contact_routes.py',
    'app/routes/campaign_routes.py',
    'app/routes/admin_routes.py'
]

for file in files:
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    content = re.sub(r'user_id=str\(current_user\.id\),\s*', "user_id=str(current_user.id), impersonator_id=getattr(current_user, 'impersonator_id', None), ", content)
    
    with open(file, 'w', encoding='utf-8') as f:
        f.write(content)
print('Done!')
