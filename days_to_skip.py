import requests
from datetime import date

# get hebrew holidays using an API

start = date(2000, 1, 1)
end = date(2029, 12, 31)

response = requests.get(
    f"https://www.hebcal.com/hebcal?v=1&cfg=json&maj=on&min=off&mod=off&nx=off&year=now&month=x&ss=off&mf=off&c=off&start={start}&end={end}")

response.raise_for_status()

items = response.json()["items"]
holidays = list(filter(lambda x: x["category"] == "holiday", items))


def is_no_work_holiday(holiday):
    if "erev" in holiday["title"].lower():
        return False

    no_work_holiday_substrings = [
        "pesach",
        "shavuot",
        "yom kippur",
        "rosh hashana",
        "sukkot",
        "atzeret",
        "torah",
    ]

    for no_work_holiday_substring in no_work_holiday_substrings:
        if no_work_holiday_substring in holiday["title"].lower():
            return True
    return False


no_work_holidays = list(filter(is_no_work_holiday, holidays))

with open("days_to_skip.csv", "w") as f:
    f.write("date,reason\n")

    for holiday in no_work_holidays:
        # NOTE: where I live, sunset *always* happens after 4pm.
        # The Hebcal.com table of holidays displays the range of dates including the day before. I ignore that day.
        # The API does not appear to list that day.
        # So, just writing the date seems to be OK.
        f.write(f"{holiday['date']},{holiday['title']}\n")
