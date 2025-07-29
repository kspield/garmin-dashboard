# garmin-dashboard


**How to set up the raspberry**

1. Flash raspberry OS with computer to SD card and set up SSH with user/password while flashing
2. Connect to GitHub - sync repo
3. Add secret key to Github and adjust code so it fits the file
4. Run scraper to get Garmin MFA
5. Set up cron to run regularly
6. Generate your Withings OAuth tokens using `Withings_Generate_Token.py`. The
   script will prompt for your `client_id`, `consumer_secret`, and redirect URL,
   then save the token JSON locally.
7. Configure Withings API credentials and run `Withings_Weight_Scrape.py` to upload Simon's data
   automatically. The script can be scheduled via cron just like the Garmin scraper.

