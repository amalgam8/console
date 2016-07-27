# Copyright 2016 IBM Corporation
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

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
    'a8_token': os.getenv('A8_CONTROLLER_TOKEN', 'local'),
    'a8_registry_url': os.getenv('A8_REGISTRY_URL', None),
    'a8_registry_token': os.getenv('A8_REGISTRY_TOKEN', None),
    'json': True
}
settings = dotdict(settings)

app = Flask(__name__, static_url_path='')
app.debug = True

@app.route('/api/v1/rules')
def get_rules():
    res = commands.rules_list(settings)
    return jsonify(rules=res)

@app.route('/api/v1/rules', methods=["POST"])
def post_rule():
    payload = request.get_json()
    args = settings
    args.source = payload["source"]
    args.destination = payload["destination"]
    args.header = payload["header"]
    args.pattern = payload["header_pattern"]
    args.delay_probability = payload["delay_probability"]
    args.delay = payload["delay"]
    args.abort_probability = payload["abort_probability"]
    args.abort_code = payload["abort_code"]
    commands.set_rule(args)
    return "", 200

@app.route('/api/v1/rules', methods=["DELETE"])
def delete_rules():
    args = settings
    commands.clear_rules(args)
    return "", 200

@app.route('/api/v1/rules/<id>', methods=["DELETE"])
def delete_rule(id):
    args = settings
    args.rule_id = id
    commands.delete_rule(args)
    return "", 200

@app.route('/api/v1/recipes', methods=["POST"])
def post_recipe():
    payload = request.get_json()
    args = settings
    args.topology = payload["topology"]
    args.scenarios = payload["scenarios"]
    args.checks = payload["checks"]
    args.run_load_script = payload["load_script"]
    args.header = payload["header"]
    args.pattern = payload["header_pattern"]
    res = commands.run_recipe(args)
    return jsonify(rules=res)

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
    else:
        args.selector = None

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
    app.run(host='0.0.0.0', port=5000, debug=True)
