# Amalgam8 UI Console

This is a prototype interface of a UI control panel that allows you to modify the routes and faults/recipes associated with a set of services registered with a8.

## Requirements

The a8 console is a python Flask application so you'll need python 2.7x and Flask installed.

## Starting the console

```
export A8_CONTROLLER_URL=http://localhost:31200
export A8_REGISTRY_URL=http://localhost:31300
python app.py
```

You can access the console UI @ http://localhost:5000

## Limitations

- Only local authorization is supported with this version
- Faults/recipes cannot be set
- There is no error/parse checking on version selector rules
