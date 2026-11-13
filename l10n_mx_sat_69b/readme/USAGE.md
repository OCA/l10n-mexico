Other modules call `lookup_taxpayer` with an RFC.

The call returns the name, SAT status and official reference when the
RFC is on the list. It returns an empty result when the RFC is not
listed or when it is a generic invoice RFC (`XAXX010101000`,
`XEXX010101000`).
