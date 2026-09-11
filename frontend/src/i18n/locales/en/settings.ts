/** Account settings and credential feedback. */
export default {
  settings: {
    title: "Settings",
    description: "Your account, interface preferences and security.",
    tabs: { account: "Account", interface: "Interface", security: "Security" },
    accountDescription:
      "Manage your personal details. Your login stays unchanged.",
    interfaceDescription:
      "Your language preference follows your account across devices.",
    securityDescription: "Use your current password to set a new one.",
    username: "Username",
    firstName: "First name",
    lastName: "Last name",
    email: "Email",
    emailHint:
      "Contact details only. Email sign-in and password recovery are not available yet.",
    language: "Preferred language",
    currentPassword: "Current password",
    newPassword: "New password",
    confirmPassword: "Confirm new password",
    passwordHint: "Use 12–128 characters. Spaces are preserved.",
    signOutWarning:
      "Changing your password signs you out on all devices, including this one.",
    save: "Save changes",
    saving: "Saving…",
    changePassword: "Change password",
    saved: "Settings saved",
    passwordChanged: "Password changed. Sign in with your new password.",
    failed: "Could not save changes. Please try again.",
    invalid: "Check the entered values.",
    mismatch: "The new passwords do not match.",
    currentInvalid: "The current password is incorrect.",
    unchanged: "Choose a password different from your current one.",
  },
} as const;
