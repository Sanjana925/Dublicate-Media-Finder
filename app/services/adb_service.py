import subprocess
import re

class ADBService:
    def run(self, args, timeout=300):
        p = subprocess.run(["adb", *args], capture_output=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr

    def devices(self):
        code, out, err = self.run(["devices"], 30)
        text = out.decode("utf-8", "replace")
        rows = []
        for line in text.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2:
                rows.append((parts[0], parts[1]))
        return rows

    @staticmethod
    def quote(s):
        return "'" + s.replace("'", "'\\''") + "'"

    def shell(self, command, timeout=300):
        code, out, err = self.run(["shell", command], timeout)
        if code:
            raise RuntimeError(err.decode("utf-8","replace") or out.decode("utf-8","replace"))
        return out.decode("utf-8","replace").strip()

    def list_directories(self, folder):
        q = self.quote(folder)
        out = self.shell(f"find {q} -mindepth 1 -maxdepth 1 -type d 2>/dev/null")
        return sorted(x for x in out.splitlines() if x.strip())

    def list_media_files(self, folder, extensions):
        q = self.quote(folder)
        terms = " -o ".join(f"-iname '*{e}'" for e in sorted(extensions))
        out = self.shell(f"find {q} -type f \\( {terms} \\) 2>/dev/null", 600)
        return [x.strip() for x in out.splitlines() if x.strip()]

    def stat(self, path):
        q = self.quote(path)
        try:
            out = self.shell(f"stat -c '%s|%Y|%F' {q} 2>/dev/null", 30)
            a = out.split("|", 2)
            return {"size": int(a[0]), "mtime": int(a[1]),
                    "type": a[2] if len(a) > 2 else ""}
        except Exception:
            return {"size": 0, "mtime": 0, "type": ""}

    def sha256(self, path):
        q = self.quote(path)
        out = self.shell(
            f"(sha256sum {q} 2>/dev/null || toybox sha256sum {q} 2>/dev/null)", 300
        )
        m = re.search(r"([0-9a-fA-F]{64})", out)
        if not m:
            raise RuntimeError("SHA-256 failed")
        return m.group(1).lower()

    def pull_bytes(self, path, timeout=120):
        code, out, err = self.run(["exec-out", "cat", path], timeout)
        if code:
            raise RuntimeError(err.decode("utf-8","replace") or "Could not read phone file")
        return out

    def delete_file(self, path):
        q = self.quote(path)
        self.shell(f"test -f {q} && rm {q}", 60)
