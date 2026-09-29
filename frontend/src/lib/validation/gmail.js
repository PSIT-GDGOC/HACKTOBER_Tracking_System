/**
 * Official Gmail validation & normalization module.
 *
 * Single source of truth for:
 * - Email normalization (trim + lowercase)
 * - Strict @gmail.com domain validation (rejects subdomains, look-alikes, trailing dots)
 * - ASCII local-part validation (rejects unicode/homoglyphs, consecutive dots)
 * - Typo detection & correction suggestions
 * - Standardized user-facing copy
 *
 * NOTE: Client-side validation is for UX and user guidance only.
 */

export const GMAIL_EXAMPLE = "rudransh@gmail.com";

export const GMAIL_MESSAGES = {
  EMPTY: "Email is required.",
  INVALID_FORMAT: "Enter a valid email address.",
  NOT_GMAIL: "Only official @gmail.com addresses are allowed.",
  EXAMPLE: `Only @gmail.com addresses are allowed. Example: ${GMAIL_EXAMPLE}`,
  TYPO_PREFIX: "Did you mean ",
  VALID: "Valid Gmail address",
  CONSECUTIVE_DOTS: "Email cannot contain consecutive dots.",
  NON_ASCII: "Email must contain standard ASCII characters only.",
  INVALID_LOCAL: "Email username must start and end with a letter or number.",
};

/**
 * Common domain typo lookup map.
 * Explicit map only, no fuzzy matching dependencies.
 */
export const GMAIL_TYPO_DOMAINS = {
  "gmial.com": "gmail.com",
  "gmai.com": "gmail.com",
  "gamil.com": "gmail.com",
  "gmail.co": "gmail.com",
  "gmail.con": "gmail.com",
  "gmail.cm": "gmail.com",
  "gmal.com": "gmail.com",
  "gmaill.com": "gmail.com",
  "gmeil.com": "gmail.com",
  "gmail.org": "gmail.com",
  "gmail.net": "gmail.com",
};

/**
 * Normalizes email by trimming surrounding whitespace and converting to lowercase.
 * @param {string} input
 * @returns {string}
 */
export function normalizeEmail(input) {
  if (typeof input !== "string") return "";
  return input.trim().toLowerCase();
}

/**
 * Validates whether an email string meets the strict official Gmail rule.
 *
 * Rules:
 * - Exactly one '@' symbol.
 * - ASCII visible characters only (blocks homograph tricks like dotless 'ı' or whitespace).
 * - Domain must equal 'gmail.com' exactly.
 * - Rejects subdomains (mail.gmail.com), look-alikes (gmail.com.evil.com), trailing dots (gmail.com.).
 * - Local part: 1-64 characters, allowed characters [a-z0-9._+-], starts and ends with letter/digit.
 * - No consecutive dots in local part.
 * - Detects common typos and returns a suggestion.
 *
 * @param {string} input
 * @returns {{ ok: true, value: string } | { ok: false, code: string, message: string, suggestion?: string }}
 */
export function validateGmail(input) {
  if (!input || typeof input !== "string" || !input.trim()) {
    return {
      ok: false,
      code: "EMPTY",
      message: GMAIL_MESSAGES.EMPTY,
    };
  }

  // Reject any whitespace within the string
  if (/\s/.test(input)) {
    return {
      ok: false,
      code: "INVALID_FORMAT",
      message: GMAIL_MESSAGES.INVALID_FORMAT,
    };
  }

  // Strict ASCII-only check (printable ASCII, no control chars or unicode homoglyphs)
  if (!/^[\x21-\x7E]+$/.test(input)) {
    return {
      ok: false,
      code: "NON_ASCII",
      message: GMAIL_MESSAGES.NON_ASCII,
    };
  }

  const normalized = normalizeEmail(input);

  // Exactly one '@' separator
  const parts = normalized.split("@");
  if (parts.length !== 2) {
    return {
      ok: false,
      code: "INVALID_FORMAT",
      message: GMAIL_MESSAGES.INVALID_FORMAT,
    };
  }

  const [localPart, domainPart] = parts;

  // Validate local part length
  if (!localPart || localPart.length < 1 || localPart.length > 64) {
    return {
      ok: false,
      code: "INVALID_FORMAT",
      message: GMAIL_MESSAGES.INVALID_FORMAT,
    };
  }

  // Local part allowed characters: [a-z0-9._+-]
  if (!/^[a-z0-9._+-]+$/.test(localPart)) {
    return {
      ok: false,
      code: "INVALID_FORMAT",
      message: GMAIL_MESSAGES.INVALID_FORMAT,
    };
  }

  // Local part must start and end with an alphanumeric character
  if (!/^[a-z0-9]/.test(localPart) || !/[a-z0-9]$/.test(localPart)) {
    return {
      ok: false,
      code: "INVALID_LOCAL",
      message: GMAIL_MESSAGES.INVALID_LOCAL,
    };
  }

  // No consecutive dots in local part
  if (/\.\./.test(localPart)) {
    return {
      ok: false,
      code: "CONSECUTIVE_DOTS",
      message: GMAIL_MESSAGES.CONSECUTIVE_DOTS,
    };
  }

  // Check typo suggestions first if domain is close
  if (GMAIL_TYPO_DOMAINS[domainPart]) {
    const suggested = `${localPart}@gmail.com`;
    return {
      ok: false,
      code: "TYPO",
      message: `${GMAIL_MESSAGES.TYPO_PREFIX}${suggested}?`,
      suggestion: suggested,
    };
  }

  // Strict domain check: must equal 'gmail.com' exactly
  if (domainPart !== "gmail.com") {
    return {
      ok: false,
      code: "NOT_GMAIL",
      message: GMAIL_MESSAGES.EXAMPLE,
    };
  }

  return {
    ok: true,
    value: `${localPart}@gmail.com`,
  };
}

/**
 * Lightweight schema validator matching standard Zod-like contract:
 * - parse(input): returns normalized email or throws
 * - safeParse(input): returns { success: true, data } or { success: false, error: { message, issues } }
 * - transform(fn): returns transformed schema
 */
export const gmailSchema = {
  safeParse(input) {
    const res = validateGmail(input);
    if (res.ok) {
      return { success: true, data: res.value };
    }
    return {
      success: false,
      error: {
        message: res.message,
        issues: [{ code: res.code, message: res.message, suggestion: res.suggestion }],
      },
    };
  },
  parse(input) {
    const res = validateGmail(input);
    if (!res.ok) {
      const err = new Error(res.message);
      err.code = res.code;
      err.suggestion = res.suggestion;
      throw err;
    }
    return res.value;
  },
  transform(transformFn) {
    return {
      ...this,
      parse: (input) => transformFn(this.parse(input)),
      safeParse: (input) => {
        const res = this.safeParse(input);
        if (!res.success) return res;
        return { success: true, data: transformFn(res.data) };
      },
    };
  },
};
