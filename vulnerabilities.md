# 🛡️ CommitGuard — Vulnerability Catalog & Test Cases

This document details the specific security loopholes and code-level vulnerabilities that CommitGuard is trained to detect. Each category includes the "loophole" (the technical flaw), the "exploit" (how it’s abused), and the "test case" (the diff the model must analyze).

---

## 1. SQL Injection (CWE-89)
**The Loophole:** Using untrusted user input directly in a database query string without parameterization or escaping.

- **The Attack:** An attacker provides input like `' OR 1=1 --` to bypass authentication or dump the entire database.
- **CommitGuard Test Case:**
  ```diff
  - cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
  + cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
  ```
- **Agentic reasoning:** The model should recognize that replacing a parameterized query (`%s`) with an f-string is a high-severity regression.

## 2. Buffer Overflow (CWE-120 / CWE-787)
**The Loophole:** Copying data into a fixed-length buffer without checking the size of the source data.

- **The Attack:** An attacker sends more data than the buffer can hold, overwriting adjacent memory to execute arbitrary code (Return-Oriented Programming).
- **CommitGuard Test Case:**
  ```diff
  - strncpy(dest, src, sizeof(dest) - 1);
  + strcpy(dest, src);
  ```
- **Agentic reasoning:** The model must identify that `strcpy` is inherently unsafe compared to the bound-checked `strncpy`.

## 3. Path Traversal (CWE-22)
**The Loophole:** Constructing a file path using user input without neutralizing `../` sequences.

- **The Attack:** An attacker provides input like `../../../../etc/passwd` to read sensitive system files.
- **CommitGuard Test Case:**
  ```diff
  - filename = os.path.basename(user_input)
  - path = os.path.join("/safe/dir", filename)
  + path = os.path.join("/safe/dir", user_input)
  ```
- **Agentic reasoning:** The model should flag the removal of `os.path.basename()` as it allows the user to break out of the intended directory.

## 4. Integer Overflow to Buffer Overflow (CWE-190)
**The Loophole:** A calculation used for memory allocation overflows, resulting in a much smaller buffer than required.

- **The Attack:** An attacker provides a large integer that causes an addition or multiplication to wrap around to a small value, leading to a heap overflow.
- **CommitGuard Test Case:**
  ```diff
  - size_t total_size = num_items * item_size;
  - if (num_items > MAX_ITEMS) return ERROR;
  + size_t total_size = num_items * item_size;
  + // Removed bounds check to support larger datasets
  ```
- **Agentic reasoning:** The model identifies that removing the `MAX_ITEMS` check makes the `total_size` calculation susceptible to wrapping.

## 5. Use-After-Free (CWE-416)
**The Loophole:** Referencing memory after it has been freed.

- **The Attack:** An attacker triggers a free and then influences the program to use that pointer, potentially leading to arbitrary code execution if the memory has been re-allocated.
- **CommitGuard Test Case:**
  ```diff
    free(buffer);
  + printf("Log: %s", buffer); // Debugging line added
  ```
- **Agentic reasoning:** The model flags the `printf` call because it accesses `buffer` immediately after `free()`.

## 6. Command Injection (CWE-78)
**The Loophole:** Passing unsanitized input to a system shell command.

- **The Attack:** An attacker provides input like `; rm -rf /` to execute arbitrary system commands.
- **CommitGuard Test Case:**
  ```diff
  - subprocess.run(["ls", folder_name])
  + os.system("ls " + folder_name)
  ```
- **Agentic reasoning:** The model recognizes that `os.system` invokes a shell and is vulnerable to concatenation-based injection, unlike the list-based `subprocess.run`.

## 7. Hardcoded Credentials (CWE-798)
**The Loophole:** Storing secrets (API keys, passwords) in the source code.

- **The Attack:** An attacker reads the leaked key from the git history and gains unauthorized access to external services.
- **CommitGuard Test Case:**
  ```diff
  - api_key = os.environ.get("STRIPE_KEY")
  + api_key = "sk_test_4eC39HqLyjWDarjtT1zdp7dc"
  ```
- **Agentic reasoning:** The model flags the change from an environment variable to a plaintext string as a security risk.

---

## 📈 Summary of Coverage
CommitGuard's RL environment is specifically designed to stress-test an agent's ability to see these patterns in **diff format**. Unlike static analysis tools (SAST) which look at the whole file, CommitGuard forces the agent to understand **what changed** and whether that change introduced one of the loopholes listed above.
