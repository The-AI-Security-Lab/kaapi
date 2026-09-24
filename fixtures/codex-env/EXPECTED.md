# Expected result

- System and user configuration are merged in documented precedence order.
- The user approval policy overrides the system value.
- Project configuration is detected but not applied because trust is not
  observed.
- The result is not a clean PASS while the project layer is unevaluated.
