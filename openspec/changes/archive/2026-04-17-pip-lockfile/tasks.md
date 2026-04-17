## 1. Create lockfile

- [x] 1.1 Rename `requirements.txt` to `requirements.in`
- [x] 1.2 Install pip-tools in the local venv (`pip install pip-tools`)
- [x] 1.3 Run `pip-compile --generate-hashes requirements.in -o requirements.txt` to generate the lockfile
- [x] 1.4 Verify the generated `requirements.txt` contains hashes for all deps

## 2. Update Dockerfile

- [x] 2.1 Change `pip install --no-cache-dir -r requirements.txt` to `pip install --no-cache-dir --require-hashes -r requirements.txt`

## 3. Update yt-dlp bump workflow

- [x] 3.1 Change the `CURRENT` grep target from `requirements.txt` to `requirements.in`
- [x] 3.2 Change the `sed` target from `requirements.txt` to `requirements.in`
- [x] 3.3 Add a step to install pip-tools and run `pip-compile --generate-hashes` after the sed update
- [x] 3.4 Update `git add` to include both `requirements.in` and `requirements.txt`
