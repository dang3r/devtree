#!/usr/bin/env bash
#
#

# Sync locally up
rclone sync text r2:devtree-private/text --progress
rclone sync pdfs r2:devtree-private/pdfs --progress
rclone sync predicates r2:devtree-private/predicates --progress