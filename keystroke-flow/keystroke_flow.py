import argparse
import json
import logging
import sqlite3

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname).01s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

# Set up parsing arguments
parser = argparse.ArgumentParser()
parser.add_argument(
    '-i', '--input',
    help='Path to the input "Network Action Predictor" database',
    required=True)
parser.add_argument(
    '-t', '--threshold',
    help='Threshold value for filtering links. URLs with a max incoming '
         'link value below this threshold will not be shown.',
    default='2.0')

# Read the inputs
args = parser.parse_args()
db_name = args.input
threshold = args.threshold

logging.info('Using Network Action Predictor database: {}'.format(db_name))
logging.info('Using a threshold of {}. URLs with a max incoming link value '
             'below this threshold will not be shown.'.format(threshold))
logging.info('Default is 2; lower it to 1 at your own risk (the data is '
             'often noisy).')
logging.info('-'*60)

# Connect to the database and read all the rows
con = sqlite3.connect(db_name)
con.row_factory = sqlite3.Row
rows = con.execute('SELECT * from network_action_predictor;')
links = []

for row in rows:

    # If the row is just a suggestion that didn't lead to a url
    if row['number_of_hits'] == 0:
        logging.debug('Skipping 0-hit row {}'.format(row['url']))
        continue

    # If the text is the same as the url (copy/paste, dedicated typist, etc)
    if row['user_text'] == row['url']:
        logging.debug('Skipping same text/url row {}'.format(row['url']))
        continue

    # Transform each remaining row into a 'link' dict, made up of a source
    # (the 'user_text' value), a target (the url), and a value (# of hits).
    links.append({'source': str(row['user_text']), 'target': str(row['url']),
                  'value': '{:.1f}'.format(row['number_of_hits'])})

shared_links = {}
for link in links:
    # If the url (link['target']) doesn't exist as a key in the shared_links
    # dict, make an entry with the url as key and an empty dict ({}) as value.
    shared_links.setdefault(link['target'], {})

    # Next we want to group the user_text entries by what url they point at.
    #
    # Populate each url's dict with a key/value containing the user_text that
    # eventually led to it being visited, and the number of times it was typed.
    #
    # Example:
    #   'https://www.youtube.com/': {
    #       'y': 5.0,
    #       'yo': 5.0,
    #       'you': 3.0
    #   }
    shared_links[link['target']][link['source']] = float(link['value'])


sankey_links = []

for url in shared_links:

    # There often are a lot of urls that have only been visited a few times.
    # These can make the graphic 'noisy', so we add the ability to filter out
    # any entries that are below a user-defined 'threshold' value.
    if max(shared_links[url].values()) < float(threshold):
        logging.debug('Skipping url ({}) that has link values '
                      'below the threshold'.format(url))
        continue

    # Now we have many user_text entries all pointing to the url they eventually
    # pointed to. This would result in a graph that's only two 'levels' deep.
    # We want to modify the links so that user_text entries that eventually
    # point to the same url and that are subsets point to each other instead,
    # showing the flow (and not over counting the end result).
    #
    # Using the same YouTube data as the example, we have these links:
    #   'y' -> youtube.com (5),
    #   'yo' -> youtube.com (5)
    #   'you' -> youtube.com (3)
    #
    # Instead of three links to youtube.com, we want to show the chain:
    #   'y' -> 'yo' (5)
    #          'yo' -> youtube.com (2)
    #          'yo' -> 'you' (3)
    #                  'you' -> youtube.com (3)
    #
    # (hard to illustrate in ascii :/)

    # Get a sorted list of all the user_text items that point to a given url
    user_text_items = sorted(shared_links[url])
    for i, user_text in enumerate(user_text_items):

        # If this isn't the last item in the list
        if len(user_text_items)-1 > i:
            next_user_text = user_text_items[i+1]

            # Check if the next user_text item is the same as the current
            # user_text, but with one letter added at the end.
            #
            # Examples:
            #   y & yo
            #   yo & you
            if next_user_text[:-1] == user_text:
                # Find the overlap in 'weight' between i and i+1
                user_text_weight = shared_links[url][user_text]
                next_user_text_weight = shared_links[url][next_user_text]
                overlap = min(user_text_weight, next_user_text_weight)

                # Make a link from i -> i+1 with the value = overlap weight
                sankey_links.append(
                  {
                    'source': user_text,
                    'target': next_user_text,
                    'value': overlap
                  }
                )
                logging.info('Added link: {} -> {} ({})'
                             .format(user_text, next_user_text, overlap))

                # If any weight is non-overlapping, make a link to the url with
                # that remaining, unused weight
                unassigned_weight = user_text_weight - overlap
                if unassigned_weight > 0:
                    sankey_links.append(
                        {
                            'source': user_text,
                            'target': url,
                            'value': unassigned_weight
                        }
                    )
                    logging.info('Added link: {} -> {} ({})'
                                 .format(user_text, url, unassigned_weight))

            # There might be a discontinuity (user might have pasted in a string or something)
            # and the prev item might not == current[:-1]. If so, append user_text->url link.
            # Example: y & youtube
            else:
                sankey_links.append(
                    {
                        'source': user_text,
                        'target': url,
                        'value': shared_links[url][user_text]
                    }
                )
                logging.info('Added link: {} -> {} ({})'
                             .format(user_text, url, shared_links[url][user_text]))

        # If this is the last text in the list, it can't be a subset, so just
        # make the link to the url
        else:
            sankey_links.append(
                {
                    'source': user_text,
                    'target': url,
                    'value': shared_links[url][user_text]
                }
            )
            logging.info('Added link: {} -> {} ({})'
                         .format(user_text, url, shared_links[url][user_text]))

# Start constructing the output JSON for the graphic
output = {'links': sankey_links}

# The JSON needs both the links (which we already have) and a separate list of
# all the nodes. To easily make the node list, we'll loop through the links
# and extract each source and target, then de-dupe them down using sets.
source_nodes = set([d['source'] for d in sankey_links])
target_nodes = set([d['target'] for d in sankey_links])
unique_nodes = source_nodes.union(target_nodes)

# Now do some massaging to get it in the right output format
json_nodes = []
for item in unique_nodes:
    json_nodes.append({'name': item})
output['nodes'] = json_nodes

# Save out the JSON
with open('sankey_nap.json', 'w') as j_out:
    json.dump(output, j_out, indent=2)

logging.info('-'*60)
logging.info('Total number of links: {}'.format(len(output['links'])))
logging.info('Total number of nodes: {}'.format(len(output['nodes'])))
