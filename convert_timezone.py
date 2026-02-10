import csv
import pytz
from datetime import datetime

input_filename = 'timezones.csv'
output_filename = 'timezones_with_offset.csv'

with open(input_filename, 'r') as infile, open(output_filename, 'w', newline='') as outfile:
    reader = csv.reader(infile)
    writer = csv.writer(outfile)

    # Write header for the output file
    writer.writerow(['timezone', 'utc_offset'])

    next(reader) # Skip the header row in the input file

    for row in reader:
        timezone_name = row[0]
        try:
            tz = pytz.timezone(timezone_name)
            # Get the offset for a specific datetime (using now() for simplicity)
            # A more robust solution might consider historical offsets
            offset = tz.utcoffset(datetime.now())
            
            # Format the offset as +H or -H
            # offset is a timedelta object
            total_seconds = offset.total_seconds()
            hours = int(total_seconds // 3600)
            
            if hours >= 0:
                formatted_offset = f'+{hours}'
            else:
                formatted_offset = f'{hours}' # hours will already have the negative sign

            writer.writerow([timezone_name, formatted_offset])
        except pytz.UnknownTimeZoneError:
            print(f"Warning: Unknown timezone '{timezone_name}'. Skipping.")
            writer.writerow([timezone_name, 'Unknown'])
        except Exception as e:
            print(f"Error processing timezone '{timezone_name}': {e}. Skipping.")
            writer.writerow([timezone_name, 'Error'])

print(f"Conversion complete. Output written to '{output_filename}'")
