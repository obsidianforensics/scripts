import argparse
import base64
import datetime
import re

CONSOLE_WIDTH = 70

parser = argparse.ArgumentParser()

parser.add_argument('snowflake', help='the snowflake value to parse')
parser.add_argument('--type', type=str, required=True, choices=['twitter', 'linkedin', 'discord', 'manual'])
parser.add_argument('--ts_bits', type=int, help='The number of bits that compromise the timestamp')
parser.add_argument(
    '--offset', type=int, default=0, help='The offset from the Unix epoch to apply to the extracted timestamp')

args = parser.parse_args()


snowflake = args.snowflake
number_of_ts_bits = args.ts_bits
epoch_offset = args.offset

if args.type == 'twitter':
    number_of_ts_bits = 42
    epoch_offset = 1288834974657

elif args.type == 'linkedin':
    number_of_ts_bits = 42
    epoch_offset = 0

elif args.type == 'discord':
    number_of_ts_bits = 42
    epoch_offset = 1420070400000

elif args.type == 'tiktok':
    number_of_ts_bits = 32
    epoch_offset = 0

elif args.type == 'manual':
    if not number_of_ts_bits:
        print("In manual mode, --ts_bits is required.")
        exit()


def center_on_console(console_line):
    return f'{console_line:^{CONSOLE_WIDTH}}'


def center_with_offset(console_line, offset):
    return f'{str(console_line)+" "*offset:^{CONSOLE_WIDTH}}'


def center_arrow_with_offset(console_line, offset):
    adjusted_offset = offset - len(console_line)
    return f'{str(console_line)+" "*adjusted_offset:^{CONSOLE_WIDTH}}'


def trim_zero_fractional_seconds(timestamp_string, number_to_trim):
    """Timestamp formats have different levels of precision; trim off extra 0s.

    Different formats may have less precision that the microseconds datetime returns.
    Trim off the appropriate number of trailing zeros from a value to not add extra,
    incorrect precision to it.

    """
    if re.search(rf'\.\d{{{6 - number_to_trim}}}0{{{number_to_trim}}}$', timestamp_string):
        return timestamp_string[:-number_to_trim]
    return timestamp_string


def decode_epoch_seconds(seconds):
    """Decode a numeric timestamp in Epoch seconds format to a human-readable timestamp.

    An Epoch timestamp (1-10 digits) is an integer that counts the number of seconds since Jan 1 1970.

    Useful values for ranges (all Jan-1 00:00:00):
      1970: 0
      2015: 1420070400
      2025: 1735689600
      2030: 1900000000

    """
    return datetime.datetime.utcfromtimestamp(float(seconds)), 'Epoch seconds'


def decode_epoch_centiseconds(centiseconds):
    """Decode a numeric timestamp in Epoch centiseconds (10 ms) format to a human-readable timestamp.

    An Epoch centisecond timestamp (1-12 digits) is an integer that counts the number of centiseconds (10 ms)
    since Jan 1 1970.

    Useful values for ranges (all Jan-1 00:00:00):
      1970: 0
      2015: 142007040000
      2025: 173568960000
      2030: 190000000000

    """
    # Trim off the 4 trailing 0s (don't add precision that wasn't in the timestamp)
    converted_ts = trim_zero_fractional_seconds(
        str(datetime.datetime.utcfromtimestamp(float(centiseconds) / 100)), 4)
    return converted_ts, 'Epoch centiseconds'


def decode_epoch_milliseconds(milliseconds):
    """Decode a numeric timestamp in Epoch milliseconds format to a human-readable timestamp.

    An Epoch millisecond timestamp (1-13 digits) is an integer that counts the number of milliseconds since Jan 1 1970.

    Useful values for ranges (all Jan-1 00:00:00):
      1970: 0
      2015: 1420070400000
      2025: 1735689600000
      2030: 1900000000000

    """
    converted_dt = datetime.datetime(1970, 1, 1) + datetime.timedelta(milliseconds=float(milliseconds))
    # Trim off the 3 trailing 0s (don't add precision that wasn't in the timestamp)
    converted_ts = trim_zero_fractional_seconds(str(converted_dt), 3)
    return converted_ts, 'Epoch milliseconds'


def decode_epoch_ten_microseconds(ten_microseconds):
    """Decode a numeric timestamp in Epoch ten-millisecond increments to a human-readable timestamp.

    An Epoch ten-microsecond increments timestamp (1-15 digits) is an integer that counts the number of ten-microsecond
    increments since Jan 1 1970.

    Useful values for ranges (all Jan-1 00:00:00):
      1970: 0
      2015: 142007040000000
      2025: 173568960000000
      2030: 190000000000000

    """
    # Trim off the trailing 0 (don't add precision that wasn't in the timestamp)
    converted_ts = trim_zero_fractional_seconds(
        str(datetime.datetime.utcfromtimestamp(float(ten_microseconds) / 100000)), 1)
    return converted_ts, 'Epoch ten-microsecond increments'


def decode_epoch_microseconds(microseconds):
    """Decode a numeric timestamp in Epoch microseconds format to a human-readable timestamp.

    An Epoch millisecond timestamp (1-16 digits) is an integer that counts the number of milliseconds since Jan 1 1970.

    Useful values for ranges (all Jan-1 00:00:00):
      1970: 0
      2015: 1420070400000000
      2025: 1735689600000000
      2030: 1900000000000000

    """
    converted_ts = str(datetime.datetime.utcfromtimestamp(float(microseconds) / 1000000))
    return converted_ts, 'Epoch microseconds'


def decode_webkit(microseconds):
    """Decode a numeric timestamp in Webkit format to a human-readable timestamp.

    A Webkit timestamp (17 digits) is an integer that counts the number of microseconds since 12:00AM Jan 1 1601 UTC.

    Useful values for ranges (all Jan-1 00:00:00):
      1970: 11644473600000000
      2015: 13064544000000000
      2025: 13380163200000000

    """
    return datetime.datetime.utcfromtimestamp((float(microseconds) / 1000000) - 11644473600), 'Webkit'


def decode_windows_filetime(intervals):
    """Decode a numeric timestamp in Windows FileTime format to a human-readable timestamp.

    A Windows FileTime timestamp (18 digits) is a 64-bit value that represents the number of 100-nanosecond intervals
    since 12:00AM Jan 1 1601 UTC.

    Useful values for ranges (all Jan-1 00:00:00):
      1970: 116444736000000000
      2015: 130645440000000000
      2025: 133801632000000000
      2065: 146424672000000000

    """
    return datetime.datetime.utcfromtimestamp((float(intervals) / 10000000) - 11644473600), 'Windows FileTime'


def decode_datetime_ticks(ticks):
    """Decode a numeric timestamp in .Net/C# DateTime ticks format to a human-readable timestamp.

    A .Net/C# DateTime ticks timestamp (18 digits) is the number of 100-nanosecond intervals that have elapsed since
    12:00:00 midnight, January 1, 0001 (0:00:00 UTC on January 1, 0001, in the Gregorian calendar), which represents
    DateTime.MinValue. It does not include the number of ticks that are attributable to leap seconds.

    A single tick represents one hundred nanoseconds or one ten-millionth of a second. There are 10,000 ticks in a
    millisecond, or 10 million ticks in a second.

    (^ from https://docs.microsoft.com/en-us/dotnet/api/system.datetime.ticks?view=netframework-4.8)

    Useful values for ranges (all Jan-1 00:00:00):
      1970: 621355968000000000
      2015: 635556672000000000
      2025: 638712864000000000
      2038: 642815136000000000

    """
    seconds = (ticks - 621355968000000000) / 10000000
    return (datetime.datetime.fromtimestamp(seconds)), 'DateTime ticks'


def guess_timestamp_format(timestamp):
    # Windows FileTime (18 digits)
    if 130645440000000000 <= timestamp <= 133801632000000000:  # 2015 <= ts <= 2025
        new_timestamp = decode_windows_filetime(timestamp)

    # .Net/C# DateTime ticks (18 digits)
    elif 635556672000000000 <= timestamp <= 638712864000000000:  # 2015 <= ts <= 2025
        new_timestamp = decode_datetime_ticks(timestamp)

    # WebKit (17 digits)
    elif 13064544000000000 <= timestamp <= 13380163200000000:  # 2015 <= ts <= 2025
        new_timestamp = decode_webkit(timestamp)

    # Epoch microseconds (16 digits)
    elif 1400070400000000 <= timestamp <= 1735689600000000:  # 2014 <= ts <= 2025
        new_timestamp = decode_epoch_microseconds(timestamp)

    # Epoch ten microsecond increments (15 digits)
    elif 140007040000000 <= timestamp <= 173568960000000:  # 2014 <= ts <= 2025
        new_timestamp = decode_epoch_microseconds(timestamp)

    # Epoch milliseconds (13 digits)
    elif 1000070400000 <= timestamp <= 1735689600000:  # 2014 <= ts <= 2025
        new_timestamp = decode_epoch_milliseconds(timestamp)

    # Epoch seconds (10 digits)
    # elif 1420070400 <= timestamp <= 1735689600:  # 2015 <= ts <= 2025
    else:
        new_timestamp = decode_epoch_seconds(timestamp)

    return new_timestamp


snowflake_length = 64

try:
    snowflake_int = int(snowflake)

except:
    snowflake_bytes = base64.urlsafe_b64decode(snowflake+'==')
    snowflake_length = len(snowflake_bytes) * 8
    snowflake_int = int.from_bytes(snowflake_bytes, 'big')

print_type = 'not specified'
if args.type:
    print_type = args.type

print(f'snowflake type: {print_type} | # of total bits: {snowflake_length} |'
      f' # of timestamp bits: {number_of_ts_bits} | epoch offset: {epoch_offset}\n')

print(center_on_console(snowflake))
print(center_arrow_with_offset('↓ to binary', 0))
print(center_on_console(f'{snowflake_int:>0{snowflake_length}b}'))

ts_split_offset = snowflake_length-number_of_ts_bits

print(center_arrow_with_offset(f'↓ taking upper {number_of_ts_bits} bits', ts_split_offset))

# Total length is 64 bits; we want the left-most x number,
# so shift the bits right 64-x to leave just what we want.
ts_bits = snowflake_int >> (snowflake_length - number_of_ts_bits)

print(center_with_offset(f'{ts_bits:>0{number_of_ts_bits}b}', ts_split_offset))

print(center_arrow_with_offset('↓ to decimal', ts_split_offset))

print(center_with_offset(int(ts_bits), ts_split_offset))

print(center_arrow_with_offset(f'↓ add epoch offset ({epoch_offset})', ts_split_offset))

epoch_adjusted_ts = int(ts_bits) + epoch_offset

print(center_with_offset(epoch_adjusted_ts, ts_split_offset))

print(center_arrow_with_offset('↓ to timestamp', ts_split_offset))

try:
    human_ts, ts_name = guess_timestamp_format(epoch_adjusted_ts)
    print(center_with_offset(f'{human_ts} ({ts_name})', ts_split_offset))
except OSError:
    print(center_with_offset('TS too big', ts_split_offset))
