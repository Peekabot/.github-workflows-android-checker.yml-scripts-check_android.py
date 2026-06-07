# Git Scavenger Hunt (Termux Edition)

Each checkpoint = one thing to type + one thing you should SEE that proves it worked.
Don't move to the next checkpoint until you see the proof. No proof = something's
off, and that's fine — just re-read the step.

Type commands exactly as shown, one line at a time, then press Enter.

---

### 🚩 Checkpoint 1 — Open your toolbox

Type:
```sh
pkg install git
```
**Proof it worked:** the screen stops scrolling and gives you back the `$` prompt,
with no red "error" text.

---

### 🚩 Checkpoint 2 — Get your "key" (access token)

You can't type your GitHub password into git anymore — it needs a special key
called a token instead.

1. On your phone's browser, go to github.com → tap your profile picture → **Settings**
2. Scroll to **Developer settings** → **Personal access tokens** → **Fine-grained tokens**
3. Tap **Generate new token**, give it access to this one repo, and check the boxes
   for "Contents" and "Pull requests" (read and write)
4. Tap generate, then **copy the long string it shows you** — that's your key

**Proof it worked:** you have a long random-looking string copied somewhere safe
(like your phone's notes app). You'll paste this in Checkpoint 3.

---

### 🚩 Checkpoint 3 — Find the treasure (clone the repo)

Type:
```sh
git clone https://github.com/peekabot/.github-workflows-android-checker.yml-scripts-check_android.py.git repo
```
- Username it asks for → your GitHub username
- Password it asks for → **paste the token from Checkpoint 2** (yes, the token goes
  in the password slot)

**Proof it worked:** you see lines like `Receiving objects... done.` and you're
back at the `$` prompt with no errors.

Then step inside it:
```sh
cd repo
```
**Proof it worked:** your prompt changes to show `repo` in it.

---

### 🚩 Checkpoint 4 — Stake your claim (make a branch)

Type:
```sh
git checkout -b my-test-branch
```
**Proof it worked:** it prints `Switched to a new branch 'my-test-branch'`.

---

### 🚩 Checkpoint 5 — Leave your mark (edit a file)

Type:
```sh
echo "edited from termux by [your name here]" >> TERMUX_GIT_PRACTICE.md
```
**Proof it worked:** type `cat TERMUX_GIT_PRACTICE.md` and you should see your
new line at the very bottom of the file.

---

### 🚩 Checkpoint 6 — Bag it (stage and commit)

Type these one at a time:
```sh
git add TERMUX_GIT_PRACTICE.md
git commit -m "Test edit from Termux"
```
**Proof it worked:** the commit prints something like
`[my-test-branch abc1234] Test edit from Termux` with a file-changed summary.

---

### 🚩 Checkpoint 7 — Send it home (push)

Type:
```sh
git push -u origin my-test-branch
```
**Proof it worked:** you see `branch 'my-test-branch' set up to track...` and a
link that looks like `https://github.com/.../pull/new/my-test-branch`.

---

### 🚩 Checkpoint 8 — Claim your prize (open a pull request)

Open that link from Checkpoint 7 in your phone's browser (or go to the repo on
github.com — it'll show a banner: "my-test-branch had recent pushes"). Tap
**Compare & pull request**, give it a title, and submit it as a **draft**.

**Proof it worked:** you land on a page titled "Test edit from Termux" with a
green/gray "Draft" label and a number like `#3` next to it.

---

## 🏆 You did it

You just cloned, branched, edited, committed, pushed, and opened a PR — entirely
from your phone. That's the whole loop. Everything else in git is a variation
on these eight moves.

## Bonus round (optional)

- `git status` → "what have I changed that isn't committed yet?"
- `git log --oneline -5` → "what are the last 5 things that happened here?"
- `git diff` → "show me my exact edits, line by line"
- `git pull origin <branch>` → "grab the newest version of a branch"
- Stuck on a push? Run `git pull --rebase origin <branch>` first, then push again.
