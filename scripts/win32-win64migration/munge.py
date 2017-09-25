#! /usr/bin/env python
# Script from bug https://bugzilla.mozilla.org/show_bug.cgi?id=1393447 written
# by nthomas to modify release blobs to implement watershed balrog rule for
# b7 to update 32 bit windows firefox users if 64 bit if their underlying
# os is 64 bit

import sys
import json

if len(sys.argv) !=2:
    print "usage: %s <release blob>" % sys.argv[0]
    print "creates <release blob>-win64-migration.json."
    sys.exit(1)

data = json.load(open(sys.argv[1]))

# mac, linux, and win32 are just visual noise, remove them
for p in data['platforms'].keys():
    if p not in ('WINNT_x86_64-msvc', 'WINNT_x86-msvc-x64'):
        del data['platforms'][p]

# remove partials from win64 because they won't apply to a win32 install
for ldata in data['platforms']['WINNT_x86_64-msvc']['locales'].itervalues():
    del ldata['partials']

# update the "32-bit Firefox on 64-bit Windows" alias to point to 64-bit Firefox
data['platforms']['WINNT_x86-msvc-x64']['alias'] = 'WINNT_x86_64-msvc'

# update the name to not stomp on the main release blob
data['name'] = data['name'] + '-win64-migration'


with open(data['name'] + '.json', 'w') as f:
    json.dump(data, f, indent=4, sort_keys=True)
