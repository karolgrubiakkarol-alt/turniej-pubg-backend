from flask import Flask, render_template, jsonify
import requests
import os  # Musimy importować 'os', aby odczytać tajny klucz
import csv  # NOWY IMPORT: Do czytania danych z Google
import io  # NOWY IMPORT: Do czytania tekstu CSV

# Stwórz aplikację Flask
app = Flask(__name__)


# ===================================================================
# NOWA FUNKCJA POMOCNICZA: Pobiera surowe dane CSV z Google
# ===================================================================
def get_google_sheet_csv():
    sheetID = "1SHS0Grk8YPGvweESfTLaS3w-HsVxq1QSDhqk3gcI4F0"
    sheetName = "Arkusz1"  # ZMIEŃ, JEŚLI NAZWA ZAKŁADKI JEST INNA
    csvUrl = f"https://docs.google.com/spreadsheets/d/{sheetID}/gviz/tq?tqx=out:csv&sheet={sheetName}"

    headers = {'Cache-Control': 'no-cache'}
    response = requests.get(csvUrl, headers=headers)
    response.raise_for_status()  # Rzuci błędem, jeśli arkusz jest niedostępny
    return response.text


# ===================================================================
# NOWA FUNKCJA POMOCNICZA: Tworzy mapę {Nick Gracza -> Nazwa Drużyny}
# ===================================================================
def create_player_team_map(csv_text):
    player_map = {}
    # Używamy csv.reader, aby poprawnie obsłużyć przecinki w nazwach
    # Usuwamy cudzysłowy, które dodaje Google
    reader = csv.reader(io.StringIO(csv_text.replace('"', '')))

    next(reader, None)  # Pomiń wiersz nagłówka

    for row in reader:
        try:
            # Kolumny na podstawie Twojej konfiguracji
            team_name = row[1].strip()  # Kolumna B
            kapitan = row[3].strip()  # Kolumna D
            gracz2 = row[5].strip()  # Kolumna F
            gracz3 = row[7].strip()  # Kolumna H
            gracz4 = row[9].strip()  # Kolumna J
            rezerwa = row[11].strip()  # Kolumna L

            if team_name:  # Dodaj tylko jeśli jest nazwa drużyny
                players = [kapitan, gracz2, gracz3, gracz4, rezerwa]
                for player in players:
                    if player:  # Dodaj tylko jeśli nick nie jest pusty
                        player_map[player] = team_name
        except IndexError:
            # Pomiń puste lub źle sformatowane wiersze na końcu arkusza
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


# --- Trasa 1: Twoja strona główna ---
@app.route('/')
def strona_glowna():
    return render_template('index.html')


# --- Trasa 2: API do pobierania listy zapisanych drużyn ---
@app.route('/api/druzyny')
def pobierz_druzyny():
    try:
        # Używamy teraz nowej funkcji pomocniczej
        csv_data = get_google_sheet_csv()
        return jsonify(data=csv_data)

    except requests.exceptions.RequestException as e:
        print(f"Błąd podczas pobierania danych z Google: {e}")
        return jsonify(error=str(e)), 500


# --- Trasa 3 (ZAKTUALIZOWANA): API do pobierania wyników meczu z PUBG ---
@app.route('/api/wyniki/<match_id>')
def pobierz_wyniki_meczu(match_id):
    # 1. Pobierz klucz API PUBG
    API_KEY = os.environ.get('PUBG_API_KEY')
    if not API_KEY:
        print("BŁĄD: Nie znaleziono klucza 'PUBG_API_KEY' w zmiennych środowiskowych!")
        return jsonify(error="Błąd konfiguracji serwera: brak klucza API"), 500

    # 2. (NOWOŚĆ) Pobierz mapowanie drużyn z Google Sheets
    try:
        print("Pobieranie mapowania drużyn z Google Sheets...")
        csv_data = get_google_sheet_csv()
        player_team_map = create_player_team_map(csv_data)
        print("Mapowanie drużyn utworzone.")
    except Exception as e:
        print(f"KRYTYCZNY BŁĄD: Nie można pobrać lub sparsować Google Sheet: {e}")
        return jsonify(error="Nie można załadować listy drużyn z Google Sheets"), 500

    # 3. Pobierz dane z API PUBG
    BASE_URL = f"https://api.pubg.com/shards/steam/matches/{match_id}"
    HEADERS = {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/vnd.api+json"
    }
    print(f"Pobieranie danych dla meczu: {match_id}...")

    try:
        response = requests.get(BASE_URL, headers=HEADERS)
        response.raise_for_status()  # Sprawdź, czy zapytanie się powiodło
        data = response.json()
        print("Dane pobrane. Przetwarzanie...")

        # 4. Przetwarzanie danych
        participants_data = {}
        results_data = []
        all_included_data = data.get('included', [])

        # Pętla 1: Zbierz dane o graczach (bez zmian)
        for item in all_included_data:
            if item.get('type') == 'participant':
                stats = item['attributes']['stats']
                participant_id = item['id']
                participants_data[participant_id] = {
                    "name": stats['name'],
                    "kills": stats['kills']
                }

        # Pętla 2: Zbierz dane o drużynach (roster) i ZMAPUJ NAZWY
        for item in all_included_data:
            if item.get('type') == 'roster':
                roster_stats = item['attributes']['stats']
                placement = roster_stats['rank']

                total_kills = 0
                team_player_names = []  # Lista nicków graczy z API PUBG

                participant_links = item['relationships']['participants']['data']
                for p_link in participant_links:
                    p_id = p_link['id']
                    if p_id in participants_data:
                        player = participants_data[p_id]
                        total_kills += player['kills']
                        team_player_names.append(player['name'])

                # =======================================================
                # !!! ZAKTUALIZOWANA LOGIKA MAPOWANIA NAZWY DRUŻYNY !!!
                # =======================================================
                team_name = None
                # Sprawdź każdego gracza z drużyny w API PUBG...
                for player_nick in team_player_names:
                    # ...i zobacz, czy mamy go w naszej mapie z Google Sheets
                    if player_nick in player_team_map:
                        team_name = player_team_map[player_nick]  # Znaleziono! Użyj nazwy z Google.
                        break  # Przestań szukać

                # Jeśli żaden gracz z drużyny nie został znaleziony w arkuszu...
                if not team_name:
                    # ...użyj nicku kapitana jako nazwy domyślnej
                    team_name = team_player_names[0] if team_player_names else "Nieznana Drużyna"
                # =======================================================

                # 5. Oblicz punkty S.U.P.E.R.
                placement_points = calculate_placement_points(placement)
                total_points = placement_points + total_kills

                results_data.append({
                    "rank": placement,  # Stary rank z API (do posortowania)
                    "team_name": team_name,  # POPRAWNA NAZWA DRUŻYNY
                    "placement_points": placement_points,
                    "kills": total_kills,
                    "total_points": total_points
                })

        # 6. Sortowanie (bez zmian)
        results_data.sort(key=lambda x: (x['total_points'], x['kills']), reverse=True)

        # 7. Aktualizacja miejsc (rank) po sortowaniu (bez zmian)
        for i, team in enumerate(results_data):
            team['rank'] = i + 1

        print("Przetwarzanie zakończone. Zwracanie JSON.")
        return jsonify(results_data)

    except requests.exceptions.RequestException as e:
        print(f"Błąd podczas pobierania danych z API PUBG: {e}")
        return jsonify(error=str(e)), 500