"""Compact platform families without inferring storefront availability."""


def platform_badges(platforms, links=()):
    groups = {}
    if any(link.get('label') == 'Steam' for link in links):
        groups['steam'] = {'icon': 'steam', 'label': 'Steam', 'names': ['Available on Steam']}
    for name in platforms:
        key = name.casefold()
        if key in ('pc', 'pc (microsoft windows)', 'pc (windows)', 'windows'):
            icon, label = 'windows', 'PC'
        elif key.startswith('playstation') or key in ('ps1', 'ps2', 'ps3', 'ps4', 'ps5', 'psp', 'ps vita'):
            icon, label = 'playstation', 'PlayStation'
        elif key.startswith('xbox'):
            icon, label = 'xbox', 'Xbox'
        elif key.startswith('nintendo switch'):
            icon, label = 'nintendoswitch', 'Switch'
        elif key.startswith('nintendo') or key in ('wii', 'wii u', 'game boy', 'game boy color', 'game boy advance', 'super nintendo entertainment system', 'family computer'):
            icon, label = 'nintendo', 'Nintendo'
        elif key in ('mac', 'macos', 'macintosh'):
            icon, label = 'apple', 'Mac'
        elif key == 'linux':
            icon, label = 'linux', 'Linux'
        else:
            icon, label = None, name
        group = groups.setdefault(icon or key, {'icon': icon, 'label': label, 'names': []})
        if name not in group['names']:
            group['names'].append(name)
    priority = {key: index for index, key in enumerate(
        ('steam', 'windows', 'playstation', 'xbox', 'nintendoswitch', 'nintendo', 'apple', 'linux'))}
    ordered = sorted(groups.values(), key=lambda group: priority.get(group['icon'], len(priority)))
    badges = [{**group, 'title': ', '.join(group['names'])} for group in ordered]
    if len(badges) > 4:
        remaining = badges[4:]
        badges = badges[:4] + [{'icon': None, 'label': f'+{len(remaining)}',
                               'title': ', '.join(item['title'] for item in remaining)}]
    return badges
