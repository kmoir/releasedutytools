#!/usr/bin/env python
import json
import logging
# strip a beta from a release blob
# written by kmoir, run like
# python strip_beta.py Firefox-56.0b12-build1 input.json output.json
# deprecated by changes to transform_balrog_blob.py

if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('beta')
    parser.add_argument('input')
    parser.add_argument('output')

    logging.basicConfig(format='%(asctime)s: %(message)s', level=logging.INFO)

    args = parser.parse_args()
    with open(args.input, 'r') as f:
        blob = json.load(f)

    # mac, linux, and win32 are just visual noise, remove them
    new_blob = blob
    for p in blob['platforms'].keys():
        if 'locales' in blob['platforms'][p].keys():
            # iterate through locales
            for l in blob['platforms'][p]['locales'].keys():
                if 'partials' in blob['platforms'][p]['locales'][l].keys():
                    partials = blob['platforms'][p]['locales'][l]['partials']
                    new_partials = partials
                    # remove specified partial from list of old partials
                    for part in partials:
                        if args.beta in part['from']:
                            new_partials.remove(part)
                    blob['platforms'][p]['locales'][l]['partials'] = new_partials

    for k in blob['fileUrls'].keys():
        if args.beta in blob['fileUrls'][k]['partials'].keys():
            del blob['fileUrls'][k]['partials'][args.beta]
        # check if the partials list is empty, if so delete that key
        #if not blob['fileUrls'][k]['partials']:
        #   del blob['fileUrls'][k]


    with open(args.output, 'wb') as f:
        json.dump(blob, f, indent=2)
