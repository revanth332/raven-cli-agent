import re
import shlex

def is_command_dangerous(command_str: str) -> bool:
    """
    Analyzes a command string to determine if it is potentially dangerous.
    Heuristics check for destructive operations like file deletions, system formatting,
    and dangerous flags. Treats parsing errors as dangerous to fail-safe.
    """
    if not command_str or not command_str.strip():
        return False
    
    # Split by command chaining operators: &&, ||, ;, |
    sub_commands = re.split(r'&&|\|\||;|\|', command_str)
    
    for sub in sub_commands:
        sub = sub.strip()
        if not sub:
            continue
            
        # Tokenize sub-command safely
        try:
            tokens = shlex.split(sub)
        except Exception:
            # Fallback to simple split if shlex fails, but be safe: return True (fail-safe)
            return True
            
        if not tokens:
            continue
            
        base_cmd = tokens[0].lower()
        
        # Clean up path separators or .exe suffix
        base_cmd_clean = re.split(r'[\\/]', base_cmd)[-1]
        if base_cmd_clean.endswith(".exe"):
            base_cmd_clean = base_cmd_clean[:-4]
            
        # Extract primary command name before any file extension or dot notation (e.g., mkfs.ext4 -> mkfs)
        base_name = base_cmd_clean.split('.')[0]
        
        # Dangerous base commands
        dangerous_commands = {
            "rm", "del", "rd", "rmdir", "shred", "wipe", 
            "format", "fdisk", "dd", "mkfs", "chown", "chmod", 'delete',
            "Get-ChildItem","Test-Path","where","attrib",
        }
        
        if base_cmd_clean in dangerous_commands or base_name in dangerous_commands:
            return True
            
        # Check for 'git rm'
        if base_cmd_clean == "git" and len(tokens) > 1 and tokens[1].lower() == "rm":
            return True
            
        # Check for dangerous flags in remaining tokens
        dangerous_flags = {"-rf", "/s", "/q", "--no-preserve-root","-c"}
        for t in tokens[1:]:
            t_low = t.lower()
            # Direct match or containing dangerous flag patterns
            if t_low in dangerous_flags:
                return True
            # Also catch combined flags like -rf or -fr (e.g. tar -xf can be safe, but rm -rf has -rf)
            if t_low.startswith("-") and not t_low.startswith("--"):
                # if it's a short flag block, check if it contains 'r' or 'f'
                # but only if the command is typically associated with file/directory operations
                # e.g., rm, or git. But since 'rm' is already dangerous, we just want to be extra careful.
                # Let's keep it simple and safe: if any flag contains both 'r' and 'f' together, or if it matches exactly.
                flag_chars = set(t_low[1:])
                if 'r' in flag_chars and 'f' in flag_chars:
                    return True
                
    return False
