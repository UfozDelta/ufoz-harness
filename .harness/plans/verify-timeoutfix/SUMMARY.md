verify-bench: escape regex now captures only [A-Za-z0-9-] after verify-/suite-, so a slug followed by > . " or \ is no longer a false escape (backends._ESCAPE_CELL). _run_cmd uses Popen + communicate(timeout) and kills the whole process tree via cells._stop_tree on timeout, so a grandchild holding the pipe cannot hang a phase (verify._run_cmd).
BUILD: pass
