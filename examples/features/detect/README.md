# Detect from URL

Generate a starter config directly from an API endpoint:

```
apibackuper detect --url https://api.example.com/v1/items --write-config
```

This writes a new `apibackuper.yaml` in the current directory with detected
pagination hints added when possible.
