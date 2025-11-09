from flask import Flask, render_template, jsonify
import requests

# Stwórz aplikację Flask
app = Flask(__name__)


# --- TWOJA STRONA GŁÓWNA ---
@app.route('/')
def strona_glowna():
    return render_template('index.html')


# --- NOWA TRASA (ROUTE) DLA TWOJEGO API ---
@app.route('/api/druzyny')
def pobierz_druzyny():
    try:
        # Ten kod Pythona łączy się z Google Sheets
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

# NIE POTRZEBUJEMY JUŻ BLOKU app.run() PONIŻEJ
# if __name__ == '__main__':
#     app.run(debug=True, port=5000)