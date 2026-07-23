# Focused Batch B shadow controller

Pinned to AFL++ commit `b9b2d374f05d82319e5e8ef278aa0fa43b91dc51`.
The six-dimensional LinUCB controller computes and updates candidates in
`shadow` mode, keeps actions unapplied, enables all rarity flags, and uses the
shared CmpLog target through `-c`.
