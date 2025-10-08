import requests
import time
import re
import pycountry

# User configuration
user_id = "YOUR_USER_ID"  # See README for instructions
_ncfa_TOKEN = "YOUR_NCFA_TOKEN"  # See README for instructions
num_duels = 200  # Number of last duels to fetch (More than ~400 will hit rate limits)
topN = 5  # Number of top/worst countries to display
min_guesses = 10  # Minimum number of guesses to consider a country in the stats

# Create a session object and set the _ncfa cookie
session = requests.Session()
session.cookies.set("_ncfa", _ncfa_TOKEN, domain="www.geoguessr.com")
session.cookies.set("_ncfa", _ncfa_TOKEN, domain="game-server.geoguessr.com")
BASE_URL = "https://www.geoguessr.com/api/v4/"  # Base URL for duel games


def fetch_game_ids(session, base_url, user_id, max_pages, num_duels):
    pagination_token = ""
    game_ids = []

    for page in range(max_pages):
        if len(game_ids) >= num_duels:
            print("Reached the desired number of duels.")
            break

        print(f"Fetching page {page + 1}")
        url = f"{base_url}feed/private"
        if pagination_token:
            url += f"?paginationToken={pagination_token}"

        response = session.get(url)
        if response.status_code != 200:
            print(f"Error fetching page {page + 1}: {response.status_code}")
            break

        data = response.json()
        if not data.get("entries"):
            print("All data fetched.")
            break

        # Extract game IDs for "Duels" game mode
        matches = re.findall(
            r'\\"gameId\\":\\"([\w\d\-]*)\\",\\"gameMode\\":\\"Duels\\"',
            response.text,
        )
        game_ids.extend(matches)
        if page == 535:
            print("Debug breakpoint reached at page 536")
        # Generate the next pagination token
        pagination_token = data["paginationToken"]
        game_ids = list(dict.fromkeys(game_ids))
        if (page + 1) % 50 == 0:
            time.sleep(1)

    # Remove duplicates and limit to the N last duels
    game_ids = list(dict.fromkeys(game_ids))[:num_duels]

    return game_ids


max_pages = 999

game_ids = fetch_game_ids(session, BASE_URL, user_id, max_pages, num_duels)
# print("Fetched game IDs:", game_ids)
print("Number of game IDs fetched:", len(game_ids))


# Function to fetch duel data
def fetch_duel_data(duel_id):
    response = session.get(f"https://game-server.geoguessr.com/api/duels/{duel_id}")
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching duel {duel_id}: {response.status_code}")
        return None


# Function to analyze duel statistics
def analyze_duel_stats(duel_data, user_id):
    country_stats = {}

    for duel in duel_data:
        if duel:
            teams = duel.get("teams", [])
            for round_data, roundResultT0, roundResultT1 in zip(
                duel.get("rounds", []),
                teams[0]["roundResults"],
                teams[1]["roundResults"],
            ):
                country = round_data["panorama"]["countryCode"]
                if teams[0]["players"][0]["playerId"] == user_id:
                    scoreBEN = roundResultT0["score"]
                    scoreADV = roundResultT1["score"]
                else:
                    scoreBEN = roundResultT1["score"]
                    scoreADV = roundResultT0["score"]
                score = scoreBEN - scoreADV
                if country:
                    if country not in country_stats:
                        country_stats[country] = [
                            0,
                            0,
                            0,
                            0,
                        ]  # [count, total_distance, total_time]
                    country_stats[country][0] += 1
                    country_stats[country][1] += score
                    if scoreBEN > scoreADV:
                        country_stats[country][2] += 1  # wins
                    elif scoreBEN < scoreADV:
                        country_stats[country][3] += 1  # losses

    # Sort countries by the number of guesses
    sorted_stats = sorted(country_stats.items(), key=lambda x: x[1][0], reverse=True)

    return sorted_stats


print("Fetching duel data...")
# Fetch the duel IDs
duel_ids = game_ids
duel_data = []
for i, duel_id in enumerate(duel_ids):
    duel = fetch_duel_data(duel_id)
    if duel:
        duel_data.append(duel)
    if (i + 1) % 200 == 0:
        time.sleep(1)

print("Duel data fetched. Analyzing statistics...")
# Analyze stats
sorted_stats = analyze_duel_stats(duel_data, user_id)


# Display stats
def get_country_name(country_code):
    try:
        country_name = pycountry.countries.get(alpha_2=country_code).name
        return country_name.split(",")[0]  # Keep only the text before the comma
    except AttributeError:
        return "Unknown Country"


if sorted_stats:
    # Filter countries based on the minimum number of guesses
    filtered_stats = [stat for stat in sorted_stats if stat[1][0] >= min_guesses]
    if filtered_stats:
        print(f"\nTop {topN} Countries by Win Rate:")
        print(
            f"{'Rank':<5}{'Country':<30}{'Win Rate (%)':<15}{'Wins':<10}{'Losses':<10}{'Guesses':<10}"
        )
        print("-" * 80)
        for rank, (country_code, stats) in enumerate(
            sorted(
                filtered_stats,
                key=lambda x: (
                    x[1][2] / (x[1][2] + x[1][3]) if (x[1][2] + x[1][3]) > 0 else 0
                ),
                reverse=True,
            )[:topN],
            start=1,
        ):
            country_name = get_country_name(country_code)
            total_games = stats[2] + stats[3]
            win_rate = (stats[2] / total_games) * 100 if total_games > 0 else 0
            print(
                f"{rank:<5}{country_name:<30}{win_rate:<15.2f}{stats[2]:<10}{stats[3]:<10}{stats[0]:<10}"
            )

        print(f"\nWorst {topN} Countries by Win Rate:")
        print(
            f"{'Rank':<5}{'Country':<30}{'Win Rate (%)':<15}{'Wins':<10}{'Losses':<10}{'Guesses':<10}"
        )
        print("-" * 80)
        for rank, (country_code, stats) in enumerate(
            sorted(
                filtered_stats,
                key=lambda x: (
                    x[1][2] / (x[1][2] + x[1][3]) if (x[1][2] + x[1][3]) > 0 else 0
                ),
            )[:topN],
            start=1,
        ):
            country_name = get_country_name(country_code)
            total_games = stats[2] + stats[3]
            win_rate = (stats[2] / total_games) * 100 if total_games > 0 else 0
            print(
                f"{rank:<5}{country_name:<30}{win_rate:<15.2f}{stats[2]:<10}{stats[3]:<10}{stats[0]:<10}"
            )
    if filtered_stats:
        print(f"\nTop {topN} Countries by Normalized Score:")
        print(f"{'Rank':<5}{'Country':<30}{'Normalized Score':<20}{'Guesses':<10}")
        print("-" * 65)
        for rank, (country_code, stats) in enumerate(
            sorted(filtered_stats, key=lambda x: x[1][1] / x[1][0], reverse=True)[
                :topN
            ],
            start=1,
        ):
            country_name = get_country_name(country_code)
            normalized_score = stats[1] / stats[0]
            print(f"{rank:<5}{country_name:<30}{normalized_score:<20.2f}{stats[0]:<10}")

        print(f"\nWorst {topN} Countries by Normalized Score:")
        print(f"{'Rank':<5}{'Country':<30}{'Normalized Score':<20}{'Guesses':<10}")
        print("-" * 65)
        for rank, (country_code, stats) in enumerate(
            sorted(filtered_stats, key=lambda x: x[1][1] / x[1][0])[:topN],
            start=1,
        ):
            country_name = get_country_name(country_code)
            normalized_score = stats[1] / stats[0]
            print(f"{rank:<5}{country_name:<30}{normalized_score:<20.2f}{stats[0]:<10}")

        print(f"\nTop {topN} Countries by Score:")
        print(f"{'Rank':<5}{'Country':<30}{'Score':<10}{'Guesses':<10}")
        print("-" * 55)
        for rank, (country_code, stats) in enumerate(
            sorted(filtered_stats, key=lambda x: x[1][1], reverse=True)[:topN],
            start=1,
        ):
            country_name = get_country_name(country_code)
            print(f"{rank:<5}{country_name:<30}{stats[1]:<10}{stats[0]:<10}")

        print(f"\nWorst {topN} Countries by Score:")
        print(f"{'Rank':<5}{'Country':<30}{'Score':<10}{'Guesses':<10}")
        print("-" * 55)
        for rank, (country_code, stats) in enumerate(
            sorted(filtered_stats, key=lambda x: x[1][1])[:topN], start=1
        ):
            country_name = get_country_name(country_code)
            print(f"{rank:<5}{country_name:<30}{stats[1]:<10}{stats[0]:<10}")
    else:
        print(f"No countries with at least {min_guesses} guesses to display.")
else:
    print("No statistics available to display.")
