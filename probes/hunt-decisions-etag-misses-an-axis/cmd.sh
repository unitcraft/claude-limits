#!/bin/sh
# Run from the repository root.
set -e
echo "== the hash is one door =="
sed -n '29,35p' src/server/etag.nv
echo
echo "== but WHICH parts go in is decided at each call site =="
sed -n '196,206p' src/server/handlers/snapshot.nv
sed -n '87,87p' src/server/handlers/config.nv
echo
echo "== the rule is stated in that very comment, and applied to one axis of two =="
echo "   axis 1 (in the tag):   include_hidden -> flag"
echo "   axis 2 (not in it):    st.disclosure  -> render_snapshot"
sed -n '57,63p' src/server/dto.nv
sed -n '216,217p' src/server/dto.nv
echo
echo "== what the plan requires of the LAN body =="
sed -n '276,277p' docs/plans/01.3-api.md
sed -n '548,549p' docs/plans/01.3-api.md
echo
echo "== and the config GET compares a tag that cannot know the level at all =="
sed -n '581,590p' src/server/handlers/config.nv
sed -n '181,187p' src/server/handlers/config.nv
