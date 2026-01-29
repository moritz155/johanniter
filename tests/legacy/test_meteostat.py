from meteostat import Point, Hourly
from datetime import datetime
import pandas as pd

# Set time period (last 2 hours)
now = datetime.now()
start = pd.Timestamp.now().floor('H') - pd.Timedelta(hours=2)
end = pd.Timestamp.now()

# Create Point for Berlin
location = Point(52.52, 13.41)

# Get hourly data
data = Hourly(location, start, end)
data = data.fetch()

print("Data fetched:")
print(data)
