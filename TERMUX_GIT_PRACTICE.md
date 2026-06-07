# Practicing git/GitHub from Termux

A cheat sheet for cloning, editing, and pushing to this repo from your phone.

## 1. One-time setup in Termux

```sh
pkg update && pkg upgrade
pkg install git
```

(Optional, only if you want to run the Python checker too: `pkg install python` then `pip install requests`.)

## 2. Get a personal access token

GitHub no longer accepts your password over the command line. Instead:

1. On github.com: Settings → Developer settings → Personal access tokens → Fine-grained tokens
2. Create one scoped to this repo with read/write access to "Contents" and "Pull requests"
3. Copy it somewhere safe (you'll paste it as your "password" when git asks)

## 3. Clone the repo

```sh
git clone https://github.com/peekabot/.github-workflows-android-checker.yml-scripts-check_android.py.git repo
cd repo
```

When prompted: username = your GitHub username, password = the token from step 2.

## 4. Make a branch and a small edit

```sh
git checkout -b my-test-branch
echo "edited from termux" >> TERMUX_GIT_PRACTICE.md
```

## 5. Commit and push

```sh
git add TERMUX_GIT_PRACTICE.md
git commit -m "Test edit from Termux"
git push -u origin my-test-branch
```

## 6. Open a pull request

Easiest from the phone browser: GitHub will show a "Compare & pull request" banner
right after the push. Tap it, fill in a title, and submit as a draft.

## 7. Pull future changes

```sh
git pull origin main
```

## Tips

- `git status` — see what's changed before you commit
- `git log --oneline -5` — see recent commits
- `git diff` — see your uncommitted edits
- If push is rejected, run `git pull --rebase origin <branch>` first, then push again
