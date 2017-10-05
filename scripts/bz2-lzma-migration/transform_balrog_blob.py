#!/usr/bin/env python
# script written by catlee in Repack updates for 56.0 RCs
# https://bugzilla.mozilla.org/show_bug.cgi?id=1393789
# 56.0 release channel users will only accept BZ2 compressed MAR files
# signed with the old SHA1 format. This script creates a release blob that
# references these files

import requests
import re
import json
import subprocess
import logging
import multiprocessing

def get_url(url):
    for _ in range(3):
        resp = requests.get(url)
        resp.raise_for_status()
        body = resp.content
        size = len(body)
        if size != int(resp.headers['content-length']):
            # Download size mismatch; retry
            logging.info("Download size mismatch for %s. %s vs %s", url, size,
                         int(resp.headers['content-length']))
            continue
        return body
    raise ValueError("Couldn't get %s" % url)


def get_hashes_url(complete_url):
    return re.sub(r'(build\d+)/.*', r'\1/SHA512SUMS', complete_url)


def get_beetmover_url(complete_url):
    return complete_url.replace('/update/',
                                '/beetmover-checksums/update/') + '.beet'


def parse_beetmover_data(beet):
    m = re.search(r'^(?P<hash>\w+) sha512 (?P<size>\d+) (?P<path>.*?)$',
                  beet, re.M)
    return m.groupdict()


def get_hashes(url):
    sha512sums = get_url(url)
    sig = get_url(url + '.asc')
    with open('sha512sums', 'wb') as f:
        f.write(sha512sums)
    with open('sha512sums.asc', 'wb') as f:
        f.write(sig)

    subprocess.check_call(['gpg', '--verify', 'sha512sums.asc', 'sha512sums'])
    retval = {}
    for line in sha512sums.split('\n'):
        line = line.strip()
        if not line:
            continue
        h, path = re.split('\s+', line, 1)
        retval[path] = h
    return retval


def get_url_size_hash(url, hashes):
    b_url = get_beetmover_url(url)
    b_data = parse_beetmover_data(get_url(b_url))
    assert b_data['hash'] == hashes[b_data['path']]

    return int(b_data['size']), b_data['hash']


def find_product(url):
    m = re.search('product=(.*?)&', url)
    return m.group(1) if m else None


def make_new_url(url, product):
    return re.sub('product=.*?&', 'product={}&'.format(product), url)


def is_a_beta_version(version):
    m = re.match('Firefox-[\.0-9]+b[0-9]+-build', version)
    return m is not None


if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('release')
    parser.add_argument('output')
    parser.add_argument('--wnp', action='store_true')

    logging.basicConfig(format='%(asctime)s: %(message)s', level=logging.INFO)

    args = parser.parse_args()
    logging.info('Getting balrog blob')
    blob = requests.get(
        'https://aus5.mozilla.org/api/v1/releases/{}'.format(args.release)
    ).json()
    blob['name'] += '-bz2'
    if args.wnp:
        blob['name'] += '-WNP'

    # Replace all the fileUrls with the bz2 names
    for channel, updates in blob['fileUrls'].iteritems():
        for update_type, urls in updates.iteritems():
            # We don't need to do anything about partials
            if update_type == 'partials':
                continue
            for prev_release, url in urls.iteritems():
                if 'download.mozilla.org' in url:
                    product = find_product(url)
                    new_url = make_new_url(url, product + '-bz2')
                else:
                    new_url = url.replace('.complete.mar', '.bz2.complete.mar')
                urls[prev_release] = new_url

    logging.info('Getting & verifying hashes')
    s_url = get_hashes_url(url)
    hashes = get_hashes(s_url)

    # Now get the file sizes / hashes
    pool = multiprocessing.Pool(16)

    tasks = []
    logging.info('Fetching mar hashes')
    for platform_name, platform_data in blob['platforms'].iteritems():
        if 'locales' not in platform_data:
            continue
        for locale_name, locale_data in platform_data['locales'].iteritems():
            for c in locale_data.get('completes', [])[:]:
                # Look in fileUrls for the URLs to use
                url = blob['fileUrls']['beta-localtest']['completes']['*']
                url = url.replace('%OS_BOUNCER%', platform_data['OS_BOUNCER'])
                url = url.replace('%OS_FTP%', platform_data['OS_FTP'])
                url = url.replace('%LOCALE%', locale_name)
                f = pool.apply_async(get_url_size_hash, (url, hashes))
                tasks.append((c, f))

    for c, f in tasks:
        size, hash = f.get()
        c['hashValue'] = hash
        c['filesize'] = size

    logging.info('Removing all beta partial updates for this release blob')
    for platform_name, platform_data in blob['platforms'].iteritems():
        if 'locales' not in platform_data:
            continue
        for locale_name, locale_data in platform_data['locales'].iteritems():
            if locale_data.get('partials'):
                platform_data['locales'][locale_name]['partials'] = \
                    [d for d in locale_data['partials'] if not is_a_beta_version(d['from'])]
    for channel in blob['fileUrls'].keys():
        if 'beta' in channel:
            del blob['fileUrls'][channel]
        else:
            updates = blob['fileUrls'][channel]
            for version in updates['partials'].keys():
                if is_a_beta_version(version):
                    del updates['partials'][version]


    if args.wnp:
        logging.info('Adding whatsnewpage config')
        blob['actions'] = 'showURL'
        blob['openURL'] = 'https://www.mozilla.org/%LOCALE%/firefox/56.0/whatsnew/?oldversion=%OLD_VERSION%'

    logging.info('Writing blob to %s', args.output)
    with open(args.output, 'wb') as f:
        json.dump(blob, f, indent=2)
