from flask import Flask, render_template, jsonify
import requests
import os  # Musimy importować 'os', aby odczytać tajny klucz

# Stwórz aplikację Flask
app = Flask(__name__)


# --- Funkcja pomocnicza do liczenia punktów S.U.P.E.R. ---
# (Na podstawie regulaminu, który mi podałeś)
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
        sheetID = "1SHS0Grk8YPGvweESfTLaS3w-HsVxq1QSDhqk3gcI4F0"
        sheetName = "Arkusz1"  # ZMIEŃ, JEŚLI NAZWA ZAKŁADKI JEST INNA
        csvUrl = f"https://docs.google.com/spreadsheets/d/{sheetID}/gviz/tq?tqx=out:csv&sheet={sheetName}"

        headers = {'Cache-Control': 'no-cache'}
        response = requests.get(csvUrl, headers=headers)
        response.raise_for_status()

        return jsonify(data=response.text)

    except requests.exceptions.RequestException as e:
        print(f"Błąd podczas pobierania danych z Google: {e}")
        return jsonify(error=str(e)), 500


# --- Trasa 3 (NOWA): API do pobierania wyników meczu z PUBG ---
@app.route('/api/wyniki/<match_id>')
def pobierz_wyniki_meczu(match_id):
    # 1. Pobierz swój tajny klucz API ze zmiennych środowiskowych Render
    API_KEY = os.environ.get('eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJqdGkiOiI2ODI1MTUwMC05ZWRmLTAxM2UtYzY0ZS00NmU0ZjNkZDQyMzciLCJpc3MiOiJnYW1lbG9ja2VyIiwiaWF0IjoxNzYyNjEzMDkxLCJwdWIiOiJibHVlaG9sZSIsInRpdGxlIjoicHViZyIsImFwcCI6InN0cm9uYXR1cm5pZWpvIn0.dEKoq_w3D4d4NUwR7yoyzvfWsPajcYhyBbakbJFONb8')

    if not API_KEY:
        print("BŁĄD: Nie znaleziono klucza PUBG_API_KEY w zmiennych środowiskowych!")
        return jsonify(error="Błąd konfiguracji serwera: brak klucza API"), 500

    BASE_URL = f"https://api.pubg.com/shards/steam/matches/{match_id}"
    HEADERS = {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/vnd.api+json"
    }

    print(f"Pobieranie danych dla meczu: {match_id}...")

    try:
        # 2. Wyślij zapytanie do API PUBG
        response = requests.get(BASE_URL, headers=HEADERS)
        response.raise_for_status()  # Sprawdź, czy zapytanie się powiodło

        data = response.json()
        print("Dane pobrane. Przetwarzanie...")

        # 3. Przetwarzanie skomplikowanych danych z PUBG
        participants_data = {}  # Słownik do mapowania ID gracza -> (Nick, Kille)
        results_data = []  # Lista na finalne wyniki drużyn

        all_included_data = data.get('included', [])

        # Pętla 1: Zbierz dane o wszystkich graczach
        for item in all_included_data:
            if item.get('type') == 'participant':
                stats = item['attributes']['stats']
                participant_id = item['id']
                participants_data[participant_id] = {
                    "name": stats['name'],
                    "kills": stats['kills']
                }

        # Pętla 2: Zbierz dane o drużynach (roster) i połącz je z graczami
        for item in all_included_data:
            if item.get('type') == 'roster':
                roster_stats = item['attributes']['stats']
                placement = roster_stats['rank']  # Miejsce (np. 1, 2, 3...)

                total_kills = 0
                team_player_names = []

                participant_links = item['relationships']['participants']['data']
                for p_link in participant_links:
                    p_id = p_link['id']
                    if p_id in participants_data:
                        player = participants_data[p_id]
                        total_kills += player['kills']
                        team_player_names.append(player['name'])

                # Użyj nicku pierwszego gracza jako nazwy teamu (API PUBG nie podaje nazwy teamu)
                # LUB jeśli masz listę teamów, możesz tu zmapować nicki do nazwy
                team_name = team_player_names[0] if team_player_names else "Nieznana Drużyna"

                # 4. Oblicz punkty S.U.P.E.R.
                placement_points = calculate_placement_points(placement)
                total_points = placement_points + total_kills

                results_data.append({
                    "rank": placement,
                    "team_name": team_name,
                    "placement_points": placement_points,
                    "kills": total_kills,
                    "total_points": total_points
                })

        # 5. Sortowanie wyników
        results_data.sort(key=lambda x: x['rank'])

        print("Przetwarzanie zakończone. Zwracanie JSON.")
        return jsonify(results_data)  # Zwróć gotową listę wyników

    except requests.exceptions.RequestException as e:
        print(f"Błąd podczas pobierania danych z API PUBG: {e}")
        return jsonify(error=str(e)), 500

    # Ten blok jest potrzebny TYLKO do testowania na Twoim komputerze
    if __name__ == '__main__':
        app.run(debug=True, port=5000)