"use strict";
var $http = window.axios;;

$(document).ready(function(){
  $http.defaults.headers.post['Content-Type'] = 'application/json';
  $http.defaults.headers.common['Accept'] = 'application/json';
  var LIST_SEPARATOR = ", ";

  var UNVERSIONED = "UNVERSIONED";
  function getVersionOptions(versions) {
    var res = []
    versions.forEach(function(v) {
      res.push(v.name);
    });

    return res;
  }

  function Service(service) {
    this.name = service ? service.name : '';
    this.href = service ? service.href : '';
    this.versions = service ? service.versions : [];
    this.defaultVersion = service ? service.default_version : UNVERSIONED;
    this.versionSelectors = service ? service.selectors : '';
    this.isActive = service ? service.is_active : false;

    this.versionText = function() {
      var instances = [];
      this.versions.forEach(function(v) {
        instances.push(v.name + "(" + v.num_instances + ")");
      });
      return instances.join(LIST_SEPARATOR);
    };

    ko.track(this);
  }

  function viewModel() {
    this.services = [];
    this.selectedService = new Service();
    this.versions = [];
    this.selectedVersion = '';
    this.selectors = '';

    this.editRoutes = function(service) {
      this.selectedService = service;
      this.versions = getVersionOptions(service.versions);
      this.selectedVersion = service.defaultVersion;
      this.selectors = service.versionSelectors;
      $('#collapseRoutes').collapse('show');
    };
    this.modifyRoutes = function() {
      this.selectors = this.selectors.trim();
      var data = { service: this.selectedService.name, default_version: this.selectedVersion, version_selectors: this.selectors };
      var config = {
        url: '/api/v1/routes',
        method: 'post',
        data: data
      }
      $http.request(config).then(function(res) {
        console.log(res);
      });

      $('#collapseRoutes').collapse('hide');
    };
    this.cancelRoutes = function() {
      this.selectedVersion = this.selectedService.defaultVersion;
      this.selectors = this.selectedService.versionSelectors;
      $('#collapseRoutes').collapse('hide');
    };

    ko.track(this);

    var self = this;

    function doPoll() {
      console.log('polling...')
      $http.request({url: '/api/v1/services'}).then(function(res) {
        if (res.status !== 200) console.log(res);
        var services = []
        res.data.services.forEach(function(service) {
          services.push(new Service(service));
        });

        services.sort(function(a,b) { return a.name > b.name;});
        self.services = services;
      });
    }

    // recursive polling approach so AJAX return in defined order
    // based on: https://techoctave.com/c7/posts/60-simple-long-polling-example-with-javascript-and-jquery
    (function poll() {
      setTimeout(function() {
        doPoll();
        poll();
      }, 5000);
    })();

    doPoll(); // initial one to get us started
  };

  ko.vm = new viewModel();
  ko.punches.enableAll();
  ko.applyBindings(ko.vm);
});