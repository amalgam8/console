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

# Implementation of Amalgam8 CLI functions

import sys
import requests
import json
import sets
from urlparse import urlparse
from prettytable import PrettyTable
import os
import urllib
import datetime, time
import pprint
from parse import compile
from gremlin import ApplicationGraph, A8FailureGenerator, A8AssertionChecker

def passOrfail(result):
    if result:
        return "PASS"
    else:
        return "FAIL"

def a8_get(url, token, headers={'Accept': 'application/json'}, showcurl=False, extra_headers={}):
    if token != "" :
        headers['Authorization'] = "Bearer " + token
    if extra_headers:
        headers=dict(headers.items() + extra_headers.items())

    if showcurl:
        curl_headers = ' '.join(["-H '{0}: {1}'".format(key, value) for key, value in headers.iteritems()])
        print "curl", curl_headers, url

    try:
        r = requests.get(url, headers=headers)
    except Exception, e:
        sys.stderr.write("Could not contact {0}".format(url))
        sys.stderr.write("\n")
        sys.stderr.write(str(e))
        sys.stderr.write("\n")
        sys.exit(2)

    if showcurl:
        print r.text

    return r

def a8_post(url, token, body, headers={'Accept': 'application/json', 'Content-type': 'application/json'}, showcurl=False, extra_headers={}):
    """
    @type body: str
    """
    if token != "" :
        headers['Authorization'] = "Bearer " + token
    if extra_headers:
        headers=dict(headers.items() + extra_headers.items())

    if showcurl:
        curl_headers = ' '.join(["-H '{0}: {1}'".format(key, value) for key, value in headers.iteritems()])
        print "REQ:", "curl -i -X POST", url, curl_headers, "--data", '\'{0}\''.format(body.replace('\'', '\\\''))

    try:
        r = requests.post(url, headers=headers, data=body)
    except Exception, e:
        sys.stderr.write("Could not POST to {0}".format(url))
        sys.stderr.write("\n")
        sys.stderr.write(str(e))
        sys.stderr.write("\n")
        sys.exit(2)

    if showcurl:
        print "RESP: [{0}]".format(r.status_code), r.headers
        print "RESP BODY:", r.text

    return r

def a8_put(url, token, body, headers={'Accept': 'application/json', 'Content-type': 'application/json'}, showcurl=False, extra_headers={}):
    """
    @type body: str
    """

    if token != "" :
        headers['Authorization'] = "Bearer " + token
    if extra_headers:
        headers=dict(headers.items() + extra_headers.items())

    if showcurl:
        curl_headers = ' '.join(["-H '{0}: {1}'".format(key, value) for key, value in headers.iteritems()])
        print "REQ:", "curl -i -X PUT", url, curl_headers, "--data", '\'{0}\''.format(body.replace('\'', '\\\''))

    try:
        r = requests.put(url, headers=headers, data=body)
    except Exception, e:
        sys.stderr.write("Could not PUT to {0}".format(url))
        sys.stderr.write("\n")
        sys.stderr.write(str(e))
        sys.stderr.write("\n")
        sys.exit(2)

    if showcurl:
        print "RESP: [{0}]".format(r.status_code), r.headers
        print "RESP BODY:", r.text

    return r

def a8_delete(url, token, headers={'Accept': 'application/json'}, showcurl=False, extra_headers={}):
    if token != "" :
        headers['Authorization'] = "Bearer " + token
    if extra_headers:
        headers=dict(headers.items() + extra_headers.items())

    if showcurl:
        curl_headers = ' '.join(["-H '{0}: {1}'".format(key, value) for key, value in headers.iteritems()])
        print "curl -X DELETE", curl_headers, url

    try:
        r = requests.delete(url, headers=headers)
    except Exception, e:
        sys.stderr.write("Could not DELETE {0}".format(url))
        sys.stderr.write("\n")
        sys.stderr.write(str(e))
        sys.stderr.write("\n")
        sys.exit(2)

    return r

def get_field(d, key):
    if key not in d:
        return '***MISSING***'
    return d[key]

def fail_unless(response, code_or_codes):
    if not isinstance(code_or_codes, list):
        code_or_codes = [code_or_codes]
    if response.status_code not in code_or_codes:
        print response
        print response.text
        sys.exit(3)

def is_active(service, default_version, instance_list):
    for instance in instance_list:
        version = version = tags_to_version(instance.get("tags"))
        if version == default_version:
            return True
    return False

def base_route_rule(destination, version, priority):
    rule = {
        "destination": destination,
        "priority": priority,
        "route": {
            "backends": [
                { "tags": [ version ] }
            ]
        }
    }
    return rule

def weight_rule(destination, default_version, weighted_vesions=[], priority=1):
    rule = base_route_rule(destination, default_version, priority)
    for version, weight in weighted_vesions:
        rule["route"]["backends"].insert(0, { "tags": [ version ], "weight": weight })
    return rule

def header_rule(destination, version, header, pattern, priority):
    rule = base_route_rule(destination, version, priority)
    rule["match"] = {
      "headers": {
        header: pattern
      }
    }
    return rule

def fault_rule(source, destination_name, destination_version, header, pattern, priority, delay=None, delay_probability=None, abort=None, abort_probability=None):
    rule = {
        "destination": destination_name,
        "priority": priority,
        "match": {
            "headers": {
                header: pattern
            }
        },
        "actions" : []
    }
    if source:
        source_name, source_version = split_service(source)
        rule["match"]["source"] = { "name": source_name }
        if source_version:
            rule["match"]["source"]["tags"] = [ source_version ]
    if delay_probability:
        action = {
            "action" : "delay",
            "probability" : delay_probability,
            "duration": delay
        }
        if destination_version:
            action["tags"] = [ destination_version ]
        rule["actions"].append(action)
    if abort_probability:
        action = {
            "action" : "abort",
            "probability" : abort_probability,
            "return_code": abort
        }
        if destination_version:
            action["tags"] = [ destination_version ]
        rule["actions"].append(action)
    return rule

def action_rule(source, destination, headers, priority, actions):
    rule = {
        "destination": destination,
        "priority": priority,
        "match": {
        },
        "actions" : actions
    }
    if source:
        source_name, source_version = split_service(source)
        rule["match"]["source"] = { "name": source_name }
        if source_version:
            rule["match"]["source"]["tags"] = [ source_version ]
    if headers:
         rule["match"]["headers"] = headers
    return rule

def split_service(input):
    colon = input.rfind(':')
    if colon != -1:
        service = input[:colon]
        version = input[colon+1:]
    else:
        service = input
        version = None
    return service, version

def tags_to_version(tags):
    #TODO: what about order of tags? need to be sorted?
    return ",".join(tags) if tags else NO_VERSION

def version_to_tags(version):
    return version.split(",")

def versioned_service_name(name, tags):
    service = name
    if tags:
       service += ":" + tags_to_version(tags)
    return service

def get_match_selector(version, match):
    selector = version + "("
    if "source" in match:
        selector += "source=" + versioned_service_name(match["source"]["name"], match["source"].get("tags"))
    if "headers" in match:
        for header, value in match["headers"].items():
            if selector[-1:] != "(":
                selector += ","
            if header == "Cookie" and value.startswith(".*?user="):
                selector += 'user="%s"' % value[len(".*?user="):]
            else:
                selector += 'header="%s:%s"' % (header, value)
    selector += ")"
    return selector 

def add_rule(sorted_rules, rule):
    for i in range(0, len(sorted_rules)):
        if sorted_rules[i]["priority"] < rule["priority"]:
            sorted_rules.insert(i, rule)
            return
    sorted_rules.append(rule)
    
def sort_rules(rule_list):
    sorted_rules = []
    for rule in rule_list:
        add_rule(sorted_rules, rule)
    return sorted_rules
            
def get_routes(routing_rules):
    default = None
    selectors = []
    routing_rules = sort_rules(routing_rules)
    for rule in routing_rules:
        route = rule["route"]
        match = rule.get("match")
        if match:
            if len(route["backends"]) == 1 and "weight" not in route["backends"][0]:
                version = tags_to_version(route["backends"][0]["tags"])
                selectors.append(get_match_selector(version, match))
            else:
                continue #TODO: future support for weighted match selectors?
        else:
            for backend in route["backends"]:
                version = tags_to_version(backend["tags"])
                if "weight" in backend:
                    selectors.append("%s(weight=%s)" % (version, backend["weight"]))
                else:
                    default = version
    return default, selectors
                         
NO_VERSION = "-untagged-"
SELECTOR_PARSER = compile("{version}({rule})")
ACTION_PARSER = compile("{version}({weight}->{action}={value})")

############################################
# CLI Commands
############################################

def service_list(args):
    res = []

    r = a8_get('{0}/v1/rules/routes'.format(args.a8_controller_url),
                args.a8_controller_token,
                showcurl=args.debug)
    fail_unless(r, 200)
    service_rules = r.json()["services"]

    registry_url, registry_token = args.a8_registry_url, args.a8_registry_token
    r = a8_get('{0}/api/v1/services'.format(registry_url), registry_token, showcurl=args.debug)
    fail_unless(r, 200)
    service_list = r.json()["services"]
    for service in service_list:
        x = {}
        x['name'] = service
        x['href'] = '{0}/api/v1/services/{1}'.format(registry_url, service)
        x['versions'] = []
        x['default_version'] = ""
        x['selectors'] = ""

        r = a8_get(x['href'], registry_token, showcurl=args.debug)
        fail_unless(r, 200)
        instance_list = r.json()["instances"]
        version_counts = {}
        for instance in instance_list:
            version = tags_to_version(instance.get("tags"))
            version_counts[version] = version_counts.get(version, 0) + 1

        for version, count in version_counts.iteritems():
            x['versions'].append({ 'name': version, 'num_instances': count})

        # get routing information for each service

        routing_rules = service_rules.get(service, [])
        default, selectors = get_routes(routing_rules)
        x['default_version'] = default if default else ""
        x['selectors'] = ", ".join(selectors)
        x['is_active'] = is_active(service, x['default_version'], instance_list)
        res.append(x)

    return res

def set_routing(args):
    if not args.default:
         print "You must specify --default"
         sys.exit(4)

    weight_list = []
    header_list = []
    if args.selector:
        for selector in args.selector:
            r = SELECTOR_PARSER.parse(selector)
            if not r:
                print "Invalid --selector value: %s" % selector
                sys.exit(5)
            version = r['version'].strip()
            rule = r['rule'].strip()
            key, sep, value = rule.partition('=')
            kind = key.strip()
            if kind == 'weight':
                weight = float(value.strip())
                weight_list.insert(0, (version, weight))
            elif kind == 'user':
                user = value.strip(' "')
                header_list.insert(0, (version, "Cookie", ".*?user=" + user))
            elif kind == 'header':
                header, sep, pattern = value.strip(' "').partition(':')
                header_list.insert(0, (version, header, pattern))
            else:
                print "Unrecognized --selector key (%s) in selector: %s" % (kind, selector)
                sys.exit(6)

    priority = 1    
    routing_request = { "rules": [ weight_rule(args.service, args.default, weight_list, priority) ] }
    
    for version, header, pattern in header_list:
        priority += 1
        routing_request["rules"].insert(0, header_rule(args.service, version, header, pattern, priority))
    
    #print json.dumps(routing_request, indent=2)
    r = a8_put('{0}/v1/rules/routes/{1}'.format(args.a8_controller_url, args.service),
               args.a8_controller_token,
               json.dumps(routing_request),
               showcurl=args.debug)
    fail_unless(r, [200,201])
    print 'Set routing rules for microservice', args.service

def delete_routing(args):
    r = a8_delete('{0}/v1/rules/routes/{1}'.format(args.a8_controller_url, args.service),
               args.a8_controller_token,
               showcurl=args.debug)
    fail_unless(r, 200)
    print 'Deleted routing rules for microservice', args.service

def rules_list(args):
    sys.stderr.write("WARNING: deprecated command. Will be removed in the future. Use action-list instead.\n")
    r = a8_get('{0}/v1/rules/actions'.format(args.a8_controller_url),
               args.a8_controller_token,
               showcurl=args.debug)
    fail_unless(r, 200)
    service_rules = r.json()["services"]
    #service_rules = { "ratings": test_fault_rules } #FB TEMP

    result_list = []
    for action_rules in service_rules.itervalues():
        for rule in sort_rules(action_rules):
            action_entry = {
                "id": rule["id"],
                "priority": rule["priority"]
            }
            if "match" in rule:
                match = rule["match"]
                if "source" in match:
                    action_entry["source"] = versioned_service_name(match["source"]["name"], match["source"].get("tags"))
                if "headers" in match:
                    for header, pattern in match["headers"].iteritems():
                        action_entry["header"] = header
                        action_entry["header_pattern"] = pattern
                        break # Ignore more than one header
            tagged_destinations = set()
            delay_set = False
            abort_set = False
            for action in rule["actions"]:
                if action["action"] == "delay":
                    if delay_set: continue # Ignore all but the first one.
                    action_entry["delay"] = action["duration"]
                    action_entry["delay_probability"] = action["probability"]
                    tagged_destinations.add(versioned_service_name(rule["destination"], action.get("tags")))
                    delay_set = True
                elif action["action"] == "abort":
                    if abort_set: continue # Ignore all but the first one.
                    action_entry["abort_code"] = action["return_code"]
                    action_entry["abort_probability"] = action["probability"]
                    tagged_destinations.add(versioned_service_name(rule["destination"], action.get("tags")))
                    abort_set = True
            action_entry["destination"] = ",".join(tagged_destinations)
            result_list.append(action_entry)
    return result_list

def set_rule(args):
    sys.stderr.write("WARNING: deprecated command. Will be removed in the future. Use action-add instead.\n")
    if not args.source or not args.destination or not args.header:
        print "You must specify --source, --destination, and --header"
        sys.exit(4)

    if not (args.delay > 0 and args.delay_probability > 0.0) and not (args.abort_code and args.abort_probability > 0.0):
        print "You must specify either a valid delay with non-zero delay_probability or a valid abort-code with non-zero abort-probability"
        sys.exit(5)

    destination_name, destination_version = split_service(args.destination)

    r = a8_get('{}/v1/rules/actions/{}'.format(args.a8_controller_url, destination_name),
                args.a8_controller_token,
                showcurl=args.debug)
    fail_unless(r, 200)
    current_rules = r.json()["rules"]
    
    pattern = '.*?'+args.pattern if args.pattern else '.*'
    delay_probability = args.delay_probability if args.delay_probability > 0 else None
    abort_probability = args.abort_probability if args.abort_probability > 0 else None
    priority = 10
    for rule in current_rules:
        if rule["priority"] >= priority:
            priority = rule["priority"] + 10

    rule = fault_rule(args.source,
                      destination_name,
                      destination_version,
                      args.header, pattern,
                      priority,
                      delay=args.delay,
                      delay_probability=delay_probability,
                      abort=args.abort_code,
                      abort_probability=abort_probability)
    
    current_rules.append(rule)
    payload = { "rules": current_rules }
    
    #print json.dumps(payload, indent=2)
    r = a8_put('{}/v1/rules/actions/{}'.format(args.a8_controller_url, destination_name),
                args.a8_controller_token,
                json.dumps(payload),
                showcurl=args.debug)
    fail_unless(r, 201)
    print 'Set fault injection rule between %s and %s' % (args.source, args.destination)

def action_list(args):
    r = a8_get('{0}/v1/rules/actions'.format(args.a8_controller_url),
               args.a8_controller_token,
               showcurl=args.debug)
    fail_unless(r, 200)
    service_rules = r.json()["services"]
    #service_rules = { "ratings": test_fault_rules } #FB TEMP

    result_list = []
    for action_rules in service_rules.itervalues():
        for rule in sort_rules(action_rules):
            action_entry = {
                "id": rule["id"],
                "destination": rule["destination"],
                "priority": rule["priority"],
                "actions": []
            }
            if "match" in rule:
                match = rule["match"]
                if "source" in match:
                    action_entry["source"] = versioned_service_name(match["source"]["name"], match["source"].get("tags"))
                if "headers" in match:
                    action_entry["headers"] = []
                    for header, pattern in match["headers"].iteritems():
                        action_entry["headers"].append(header + ":" + pattern)
            for action in rule["actions"]:
                version = tags_to_version(action.get("tags"))
                if action["action"] == "delay":
                    action_entry["actions"].append("%s(%s->delay=%s)" % (version, action["probability"], action["duration"]))                     
                elif action["action"] == "abort":
                    action_entry["actions"].append("%s(%s->abort=%s)" % (version, action["probability"], action["return_code"]))                     
            result_list.append(action_entry)
    return result_list

def add_action(args):
    if not args.destination or not (args.source or args.header or args.cookie):
        print "You must specify --destination, and at least one --source, --header, or --cookie parameter"
        sys.exit(4)

    if not args.action:
        print "You must specify at least one --action parameter"
        sys.exit(5)

    r = a8_get('{}/v1/rules/actions/{}'.format(args.a8_controller_url, args.destination),
                args.a8_controller_token,
                showcurl=args.debug)
    fail_unless(r, 200)
    current_rules = r.json()["rules"]
    
    if args.priority:
        priority = int(args.priority)
    else:
        priority = 10
        for rule in current_rules:
            if rule["priority"] >= priority:
                priority = rule["priority"] + 10

    if args.header or args.cookie:
        headers = {}
        if args.header:
            for header in args.header:
                key, sep, value = header.partition(':')
                headers[key] = value
        if args.cookie:
            for cookie in args.cookie:
                headers['Cookie'] = '.*?'+cookie
    else:
        headers = None
        
    actions = []
    for action in args.action:
        r = ACTION_PARSER.parse(action)
        if not r:
            print "Invalid --action value: %s" % action
            sys.exit(6)
        version = r['version'].strip()
        weight = float(r['weight'].strip())
        action_type = r['action'].strip()
        value = r['value'].strip()
        if action_type == 'delay':
            rule_action = {
                "action" : "delay",
                "probability" : weight,
                "duration": float(value),
                "tags": version_to_tags(version)
            }
            actions.append(rule_action)
        elif action_type == 'abort':
            rule_action = {
                "action" : "abort",
                "probability" : weight,
                "return_code": int(value),
                "tags": version_to_tags(version)
            }
            actions.append(rule_action)
        else:
            print "Invalid --action type: %s" % action
            sys.exit(7)
            
    rule = action_rule(args.source,
                       args.destination,
                       headers,
                       priority,
                       actions)
    
    current_rules.append(rule)
    payload = { "rules": current_rules }
    
    #print json.dumps(payload, indent=2)
    r = a8_put('{}/v1/rules/actions/{}'.format(args.a8_controller_url, args.destination),
                args.a8_controller_token,
                json.dumps(payload),
                showcurl=args.debug)
    fail_unless(r, 201)
    print 'Set action rule for destination %s' % args.destination

def clear_rules(args):
    sys.stderr.write("WARNING: deprecated command. Will be removed in the future. Use rule-delete instead.\n")
    r = a8_get('{0}/v1/rules/actions'.format(args.a8_controller_url),
               args.a8_controller_token,
               showcurl=args.debug)
    fail_unless(r, 200)
    service_rules = r.json()["services"]
    #service_rules = { "ratings": test_fault_rules } #FB TEMP

    for destination in service_rules:
        r = a8_delete('{0}/v1/rules/actions/{1}'.format(args.a8_controller_url, destination),
                      args.a8_controller_token,
                      showcurl=args.debug)
    fail_unless(r, 200)
    print 'Cleared fault injection rules from all microservices'

def delete_rule(args):
    r = a8_delete('{}/v1/rules?id={}'.format(args.a8_controller_url, args.id),
                  args.a8_controller_token,
                  showcurl=args.debug)
    fail_unless(r, 200)
    print 'Deleted fault injection rule with id: %s' % args.id

def _print_assertion_results(results):
    x = PrettyTable(["AssertionName", "Source", "Destination", "Result", "ErrorMsg"])
    x.align = "l"
    newlist={}
    for res in results:
        res['result']=passOrfail(res['result'])
    #pprint.pprint(results)
    for check in results:
        x.add_row([get_field(check, 'name'),
                   get_field(check, 'source'),
                   get_field(check, 'dest'),
                   get_field(check, 'result'),
                   get_field(check, 'errormsg')
        ])
    return x

def run_recipe(args):
    if not args.topology or not args.scenarios:
        print "You must specify --topology and --scenarios"
        sys.exit(4)

    if args.header:
        header = args.header
    else:
        header = "X-Request-ID"

    if args.pattern:
        pattern = args.pattern
    else:
        pattern = '*'

    if not args.topology:
        print u"Topology required"
        sys.exit(4)

    if not args.scenarios:
        print u"Failure scenarios required"
        sys.exit(4)

    if args.checks and not args.checks:
        print u"Checklist file required"
        sys.exit(4)

    print args.topology

    topology = ApplicationGraph(json.loads(args.topology))
    scenarios = json.loads(args.scenarios)
    checklist = json.loads(args.checks)

    fg = A8FailureGenerator(topology, a8_controller_url='{0}/v1/rules'.format(args.a8_controller_url), a8_controller_token=args.a8_controller_token,
                            header=header, pattern='.*?'+pattern, debug=args.debug)
    fg.setup_failures(scenarios)
    start_time = datetime.datetime.utcnow().isoformat()
    print start_time
    print 'Inject test requests with HTTP header %s matching the pattern %s' % (header, pattern)

    #return json.dumps({ "start_time": start_time, "header": header, "pattern": pattern, "checks": checklist })
    return json.dumps({ "trace_log_value": fg.get_id(), "checks": checklist })
        
def validate_recipe(args):
        checklist = args.checks

        time.sleep(15)
        end_time=datetime.datetime.utcnow().isoformat()
        print end_time
        #sleep for some more time to make sure all logs have been flushed
        time.sleep(5)
        log_server = checklist.get('log_server', args.a8_log_server)
        print "log_server: %s" % log_server
        log_server = args.a8_log_server
        #ac = A8AssertionChecker(es_host=log_server, header=args.header, pattern=args.pattern, start_time=args.start_time, end_time=end_time, debug=args.debug)
        ac = A8AssertionChecker(es_host=log_server, trace_log_value=args.trace_log_value, index=["_all"])      
        results = ac.check_assertions(checklist, continue_on_error=True)

        clear_rules(args)
        #print json.dumps(results, indent=2)
        return results

        # for check in results:
        #     print 'Check %s %s %s' % (check.name, check.info, passOrfail(check.success))
        # if not check.success:
        #     exit_status = 1
        # sys.exit(exit_status)
