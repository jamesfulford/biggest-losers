# biggest-losers

TODO: add instructions on how to set up.

# Troubleshooting

## My TD Token is not refreshing / has expired

Follow instructions here to generate a new token using the server: https://github.com/jamesfulford/td-token

Then, scp the token to the remote server so it can be refreshed as needed.

```bash
scp output/token.json solomon:~/td-cash-data/inputs/td-token/output/token.json
```

(There might be issues with 2 different refreshers using the same tokens, it seems refreshing might cause expiration)
