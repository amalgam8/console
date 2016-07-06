from flask import Flask, json, jsonify, make_response, request
import commands
import os
#import json

# http://stackoverflow.com/a/23689767/2422749
class dotdict(dict):
    """"dot.notation access to dictionary attributes"""
    def __getattr__(self, attr):
        return self.get(attr)
    __setattr__= dict.__setitem__
    __delattr__= dict.__delitem__

settings = {
    'debug': os.getenv('A8_DEBUG')=='1',
    'a8_url': os.getenv('A8_CONTROLLER_URL', 'http://localhost:31200'),
    'a8_token': os.getenv('A8_CONTROLLER_TOKEN', '12345'),
    'a8_tenant_id': os.getenv('A8_CONTROLLER_TENANT_ID', 'local'),
    'a8_registry_url': os.getenv('A8_REGISTRY_URL', None),
    'a8_registry_token': os.getenv('A8_REGISTRY_TOKEN', None)
}
settings = dotdict(settings)

app = Flask(__name__, static_url_path='')
app.debug = True

@app.route('/api/v1/services')
def get_services():
  res = commands.service_list(settings)
  return jsonify(services=res)

@app.route('/api/v1/routes', methods=["POST"])
def post_route():
    payload = request.get_json()
    args = settings
    args.service = payload["service"]
    args.default = payload["default_version"]
    if payload.get('version_selectors'):
        args.selector = payload["version_selectors"].split(",")

    commands.set_routing(args)
    return "", 200

@app.route('/')
@app.route('/services')
def home():
    ctx = {}
    # return send_file('templates/template.html')
    return make_response(open('templates/template.html').read())

@app.route('/about')
def about():
    return render_template('about.html')
if __name__ == '__main__':
  app.run(debug=True)
