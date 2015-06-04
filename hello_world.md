### Building a simple listener

Here we are going to write a listener that prints 'Hello world!' for every message in Normalized BuildBot ("exchange/build/normalized") with topic "#".

1) Add a file called `normalizedhello.py` to handlers/ containing:
```

    # Handler functions must receive (data, message, dry_run) as arguments
    def on_build_event(data, message, dry_run):
        print "Hello World!"

        # We need to ack the message to remove it from our pulse queue
        message.ack()
```
2) Add the following to `handlers/config.py`:
```
    import normalizedhello
```

In config.py, also add a new key in `HANDLERS_BY_EXCHANGE`:

```
    "exchange/build/normalized": {
        "topic": {
            "#": normalizedhello.on_build_event
        }
    }
```
3) Replace the content of `run_time_config.json` with:
```
    {
        "exchange": "exchange/build/normalized",
        "topic": "#"
    }
```
4) And we are done! To run, just type `run-pulse-actions`.
