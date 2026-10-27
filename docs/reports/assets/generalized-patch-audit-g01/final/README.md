# Final G1 evidence

Final tested implementation: `fd043ce9913287fe1b3e97fddedf741c8bf3ed35`.

The API-only reports come from `f59b3b1d3b8feba9ea8feb8bda0d4e8fabf5c552`.
The subsequent source change is limited to UI runtime readiness and its controlled browser
regression; backend execution/admission, runtime images and engine identity are unchanged.
The browser reports, full local regression, recovery and CI validate the final implementation.
`external-execution-index.json` records exact implementation and execution identities.

All evidence is real execution output except the explicitly synthetic offline fixtures used
by normal CI. Source bytes and upstream MIT licenses are embedded in the downloaded JSON.
The negative control is explicitly authored; API/browser reruns do not count as new discoveries.
Independent verification is not configured.

`completion-evidence-audit.json` validates all six reports, downloads/reopens them after final
recovery, and checks actual container/volume absence. `preservation.json` compares historical
files plus actual API/broker/backend/frontend bytes with the final implementation.

`manifest.json` hashes this directory's selected files and excludes itself. Earlier evidence
is preserved byte-for-byte in the parent and validation-guard directories, including failures.
