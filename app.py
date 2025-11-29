from flask import Flask, render_template, jsonify
import requests
import os
import csv
import io

# Stwórz aplikację Flask
app = Flask(__name__)


# ===================================================================
# FUNKCJA POMOCNICZA: Pobiera surowe dane CSV z Google
# ===================================================================
def get_google_sheet_csv():
    sheetID = "1SHS0Grk8YPGvweESfTLaS3w-HsVxq1QSDhqk3gcI4F0"
    sheetName = "Arkusz1"
    csvUrl = f"https://docs.google.com/spreadsheets/d/{sheetID}/gviz/tq?tqx=out:csv&sheet={sheetName}"

    headers = {'Cache-Control': 'no-cache'}
    response = requests.get(csvUrl, headers=headers)
    response.raise_for_status()
    return response.text


# ===================================================================
# FUNKCJA POMOCNICZA: Tworzy mapę {Nick Gracza -> Nazwa Drużyny}
# ===================================================================
def create_player_team_map(csv_text):
    player_map = {}
    reader = csv.reader(io.StringIO(csv_text.replace('"', '')))

    next(reader, None)  # Pomiń nagłówek

    for row in reader:
        try:
            # Sprawdź czy wiersz ma wystarczającą długość, aby uniknąć błędów
            if not row or len(row) < 2:
                continue

            team_name = row[1].strip()  # Kolumna B

            # Pobieranie graczy z zabezpieczeniem przed brakiem kolumn
            kapitan = row[3].strip() if len(row) > 3 else ""
            gracz2 = row[5].strip() if len(row) > 5 else ""
            gracz3 = row[7].strip() if len(row) > 7 else ""
            gracz4 = row[9].strip() if len(row) > 9 else ""

            # --- TUTAJ JEST KLUCZOWA ZMIANA DLA REZERWOWEGO ---
            # Sprawdzamy czy wiersz jest wystarczająco długi (ma kolumnę L/indeks 11)
            rezerwa = row[11].strip() if len(row) > 11 else ""

            if team_name:
                players = [kapitan, gracz2, gracz3, gracz4, rezerwa]
                for player in players:
                    if player:
                        # Zapisujemy nick małymi literami (.lower()), aby uniknąć problemów
                        # typu "Player1" w arkuszu vs "player1" w grze.
                        player_map[player.lower()] = team_name
        except Exception as e:
            print(f"Pominięto wiersz z powodu błędu: {e}")
            continue

    return player_map


# --- Funkcja pomocnicza do liczenia punktów S.U.P.E.R. ---
def calculate_placement_points(rank):
    if rank == 1:
        return 10
    elif rank == 2:
        return 6
    elif rank == 3:
        return 5
    elif rank == 4:
        return 4
    elif rank == 5:
        return 3
    elif rank == 6:
        return 2
    elif rank in [7, 8]:
        return 1
    else:
        return 0


# --- Trasa 1: Strona główna ---
@app.route('/')
def strona_glowna():
    return render_template('index.html')


# --- Trasa 2: API lista drużyn ---
@app.route('/api/druzyny')
def pobierz_druzyny():
    try:
        csv_data = get_google_sheet_csv()
        return jsonify(data=csv_data)
    except requests.exceptions.RequestException as e:
        return jsonify(error=str(e)), 500


# --- Trasa 3: API wyniki meczu ---
@app.route('/api/wyniki/<match_id>')
def pobierz_wyniki_meczu(match_id):
    API_KEY = os.environ.get('PUBG_API_KEY')
    if not API_KEY:
        return jsonify(error="Błąd konfiguracji: brak klucza API"), 500

    # 1. Pobierz mapowanie (z obsługą rezerwowych)
    try:
        csv_data = get_google_sheet_csv()
        player_team_map = create_player_team_map(csv_data)
    except Exception as e:
        return jsonify(error="Nie można załadować listy drużyn"), 500

    # 2. Pobierz dane z PUBG
    BASE_URL = f"https://api.pubg.com/shards/steam/matches/{match_id}"
    HEADERS = {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/vnd.api+json"
    }

    try:
        response = requests.get(BASE_URL, headers=HEADERS)
        response.raise_for_status()
        data = response.json()

        participants_data = {}
        results_data = []
        all_included_data = data.get('included', [])

        # Zbieranie danych o poszczególnych graczach
        for item in all_included_data:
            if item.get('type') == 'participant':
                stats = item['attributes']['stats']
                participants_data[item['id']] = {
                    "name": stats['name'],
                    "kills": stats['kills']
                }

        # Zbieranie danych o drużynach (rosterach)
        for item in all_included_data:
            if item.get('type') == 'roster':
                roster_stats = item['attributes']['stats']
                placement = roster_stats['rank']
                total_kills = 0
                team_player_names = []

                # Sumowanie killi dla wszystkich graczy w tym rosterze
                # (Jeśli grał rezerwowy, API PUBG go tu uwzględni i kille zostaną dodane)
                participant_links = item['relationships']['participants']['data']
                for p_link in participant_links:
                    p_id = p_link['id']
                    if p_id in participants_data:
                        player = participants_data[p_id]
                        total_kills += player['kills']
                        team_player_names.append(player['name'])

                # Identyfikacja nazwy drużyny
                team_name = None
                for player_nick in team_player_names:
                    # Sprawdzamy nick małymi literami (.lower())
                    if player_nick.lower() in player_team_map:
                        team_name = player_team_map[player_nick.lower()]
                        break

                if not team_name:
                    team_name = team_player_names[0] if team_player_names else "Nieznana Drużyna"

                placement_points = calculate_placement_points(placement)
                total_points = placement_points + total_kills

                results_data.append({
                    "rank": placement,
                    "team_name": team_name,
                    "placement_points": placement_points,
                    "kills": total_kills,
                    "total_points": total_points
                })

        # Sortowanie wyników
        results_data.sort(key=lambda x: (x['total_points'], x['placement_points']), reverse=True)

        # Nadawanie miejsc po sortowaniu
        for i, team in enumerate(results_data):
            team['rank'] = i + 1

        return jsonify(results_data)

    except requests.exceptions.RequestException as e:
        return jsonify(error=str(e)), 500