# OpenConnect [Try it now!](https://share.streamlit.io/anthonymockler/openconnect/main/interactive.py)
An interactive app for visualising and assessing School / Health Centre connectivity


## Data Sources

* Facility Location Data from [OpenStreetMap](https://openstreetmap.org)
* Internet Connectivity Estimates from [Ookla/Speedtest.net](https://registry.opendata.aws/speedtest-global-performance/)

## Methods
* OSM Data is parsed by 'amenity=school/hospital' - OSM Data may be very complete or very incomplete depending on your chosen country
* Ookla Speedtests are aggregated to the Bing Tile 14 level for the sake of speed, Bing Tile 16 would be better, but needs a bigger database


## Notes / TODO
* Using the 'fixed-line' dataset only from Ookla. Mobile may be relevant, but hard to pinpoint if a mobile speed test is actually from the relevant facility
* Facilities labelled 'No connectivity' are in tiles that don't have at least 4 Ookla speedtests in the last 12 months.
* Should also provide summary stats by Administrative region?


