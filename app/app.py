from flask import Flask, render_template, send_from_directory, request
import os

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/submit_text', methods=['POST'])
def submit_text():
    text = request.form['userInput']
    # Here, you can process the text as needed
    print(text)  # Example action: print the text
    return 'Text received: ' + text  # Sends a response back to the browser

@app.route('/tracks')
def tracks():
    return render_template('tracks.html')

@app.route('/remap')
def remap():
    return render_template('remap.html')

@app.route('/browser')
def browser():
    base_path = "../files"
    files = os.listdir(base_path)
    return render_template('browser.html', files=files, base_path=base_path)

@app.route('/files/<path:filename>')
def file(filename):
    # Send files from the directory
    return send_from_directory('../files', filename)

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/settings')
def settings():
    return render_template('settings.html')

@app.route('/help')
def help():
    return render_template('help.html')




if __name__ == "__main__":
    app.run(debug=True,host='0.0.0.0', port=5000)
