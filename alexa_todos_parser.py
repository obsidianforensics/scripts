import sqlite3
import json
import xlsxwriter
import sys
import datetime
import time


def to_human_timestamp(timestamp):
    if timestamp:
        new_timestamp = datetime.datetime.utcfromtimestamp(float(timestamp) / 1000)
        return new_timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    else:
        return ""

print("="*78)
print("| {:^74} |".format("Alexa To-Dos Parser v0.1"))
print("="*78)

if len(sys.argv) < 2:
    print("Usage: alexa_todos_parser.py LocalData.sqlite")
    sys.exit(0)

if len(sys.argv) >= [2]:
    output = sys.argv[2]
else:
    output = "Alexa To-Do List Items ({})".format(time.strftime('%Y-%m-%dT%H-%M-%S'))

local_data_path = sys.argv[1]
print("\n * Reading data from {}\n".format(sys.argv[1]))

workbook = xlsxwriter.Workbook("{}.xlsx".format(output))
w = workbook.add_worksheet('Items')

# Define cell formats
title_header_format  = workbook.add_format({'font_color': 'white', 'bg_color': 'gray', 'bold': 'true'})
header_format        = workbook.add_format({'font_color': 'black', 'bg_color': 'gray', 'bold': 'true'})
black_type_format    = workbook.add_format({'font_color': 'black', 'align': 'left'})
black_date_format    = workbook.add_format({'font_color': 'black', 'num_format': 'yyyy-mm-dd hh:mm:ss.000'})

# Title bar
w.merge_range('A1:M1', "Alexa To-Do List Items", title_header_format)

# Write column headers
w.write(1, 0, "Item",                     header_format)
w.write(1, 1, "nBestItems",               header_format)
w.write(1, 2, "Complete",                 header_format)
w.write(1, 3, "Deleted",                  header_format)
w.write(1, 4, "Type",                     header_format)
w.write(1, 5, "Created Date",             header_format)
w.write(1, 6, "Last Updated Date",        header_format)
w.write(1, 7, "Last Local Updated Date",  header_format)
w.write(1, 8, "Reminder Time",            header_format)
w.write(1, 9, "Item ID",                  header_format)
w.write(1, 10, "Customer ID",             header_format)
w.write(1, 11, "Utterance ID",            header_format)
w.write(1, 12, "Original Audio ID",       header_format)

# Set column widths
w.set_column('A:A', 32)
w.set_column('B:B', 40)
w.set_column('C:C', 12)
w.set_column('D:D', 12)
w.set_column('E:E', 16)
w.set_column('F:F', 22)
w.set_column('G:G', 22)
w.set_column('H:H', 22)
w.set_column('I:I', 22)
w.set_column('J:J', 56)
w.set_column('K:K', 18)
w.set_column('L:L', 22)
w.set_column('M:M', 108)

local_data_db = sqlite3.connect(local_data_path)
local_data_db.row_factory = sqlite3.Row

row_number = 2

display_row_format = "| {:<36} | {:^16} | {:^16} |"

print("-"*78)
print(display_row_format.format("ToDo Text", "Created", "LastUpdated"))
print("-"*78)

# Open the 'LocalData.sqlite file
with local_data_db:
    c = local_data_db.cursor()

    # Select the rows where ZKEY starts with 'ToDoCollections' - there should only be two, ToDoCollection.TASK and
    # ToDoCollection.SHOPPING_ITEM
    c.execute("SELECT ZVALUE FROM ZDATAITEM WHERE ZKEY LIKE 'ToDoCollection%'")

    # For both the rows we selected with the above query, we want to:
    for row in c.fetchall():
        # load the contents of ZDATAITEM as a JSON, since it makes it easy to work with
        row_json = json.loads(row[0])

        # for each item in the JSON, write values to XLSX file
        for item in row_json:
            # the text that was added to the ToDoCollection
            w.write(row_number, 0, item['text'], black_type_format)

            # the nbestItems seem to be the "runner-up" translations that Alexa heard but decided against using. If text
            # was entered via app, this will be empty.
            if item['nbestItems']:
                # there are often more than one of these, so join them all together for display
                nbestItems_string = ", ".join(item['nbestItems'])
                w.write(row_number, 1, nbestItems_string, black_type_format)

            # if the item has been completed - TRUE or FALSE
            w.write(row_number, 2, item['complete'], black_type_format)

            # if the item has been deleted - TRUE or FALSE
            w.write(row_number, 3, item['deleted'], black_type_format)

            # the item type - either TASK or SHOPPING_ITEM
            w.write(row_number, 4, item['type'], black_type_format)

            # item creation timestamp - in JSON as 1463950942522, but gets converted to 2016-05-22 21:02:22.522
            w.write(row_number, 5, to_human_timestamp(item['createdDate']), black_date_format)

            # item update timestamp - in JSON as 1463950942522, but gets converted to 2016-05-22 21:02:22.522
            w.write(row_number, 6, to_human_timestamp(item['lastUpdatedDate']), black_date_format)

            # item local update timestamp - presumably is set if the item is checked off/changed on the mobile device
            w.write(row_number, 7, to_human_timestamp(item['lastLocalUpdatedDate']), black_date_format)

            # reminder time - I presume this is the same as others, but I hadn't used this feature so no data
            w.write(row_number, 8, to_human_timestamp(item['reminderTime']), black_date_format)

            # long string, appears to be customer ID concatenated with a GUID separated by #
            # example: A1C9VTA5F7ZW1N#28a70937-7525-313f-a58c-374d73f91505
            w.write(row_number, 9, item['itemId'], black_type_format)

            # customer ID, same as above - A1C9VTA5F7ZW1N - was static for all my test data (which is expected)
            w.write(row_number, 10, item['customerId'], black_type_format)

            # not quite sure - was null for all my entries
            w.write(row_number, 11, item['utteranceId'], black_type_format)   # record_type

            # originalAudioId - looks to be unique per entry. Not sure of make up; 2016/04/18/19 correspond to
            # YYYY/MM/DD/HH of createdDate, first string (up to #) is static but != customerId, and GUID toward
            # end != itemId. Example:
            # AB72C64C86AW2:1.0/2016/04/18/19/B0F00715549602C4/04:29::TNIH_2V.275ba59c-49a7-45fa-b484-b21435c8ebc7ZXV/0
            w.write(row_number, 12, item['originalAudioId'], black_type_format)   # record_type

            row_number += 1
            try:
                print(display_row_format.format(item['text'], to_human_timestamp(item['createdDate'])[:16], to_human_timestamp(item['lastUpdatedDate'])[:16]))
            except:
                print("| {:^74} |".format("< Error printing row; check XLSX output >"))

    print("-" * 78)
    print(" * Parsed {} ToDo items".format(row_number-1))
    print(" * Saved XLSX output to {}".format(output))

    # Formatting
    w.freeze_panes(2, 0)                # Freeze top row
    w.autofilter(1, 0, row_number, 16)  # Add autofilter

workbook.close()
