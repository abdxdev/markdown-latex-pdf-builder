--
-- This is file `pre_append_to_vlist_filter.lua',
-- generated with the docstrip utility.
--
-- The original source files were:
--
-- lua-ul.dtx  (with options: `callback')
-- 
-- Copyright (C) 2020-2024 by Marcel Krueger
--
-- This file may be distributed and/or modified under the
-- conditions of the LaTeX Project Public License, either
-- version 1.3c of this license or (at your option) any later
-- version. The latest version of this license is in:
--
-- http://www.latex-project.org/lppl.txt
--
-- and version 1.3 or later is part of all distributions of
-- LaTeX version 2005/12/01 or later.
if luatexbase.callbacktypes.pre_append_to_vlist_filter then
  return
end

local call_callback = luatexbase.call_callback
local flush_node = node.flush_node
local prepend_prevdepth = node.prepend_prevdepth
local callback_define

do
  local saved_luatexbase, saved_callback_register = luatexbase, callback.register
  luatexbase.uninstall()
  callback_define = callback.register
  luatexbase, callback.register = saved_luatexbase, saved_callback_register
end

local function filtered_append_to_vlist_filter(box,
                                               locationcode,
                                               prevdepth,
                                               mirrored)
  local current = call_callback("pre_append_to_vlist_filter",
                                box, locationcode, prevdepth,
                                mirrored)
  if not current then
    flush_node(box)
    return
  elseif current == true then
    current = box
  end
  return call_callback("append_to_vlist_filter",
                       current, locationcode, prevdepth, mirrored)
end

callback_define('append_to_vlist_filter',
                filtered_append_to_vlist_filter)
luatexbase.callbacktypes.append_to_vlist_filter = nil
luatexbase.create_callback('append_to_vlist_filter', 'exclusive',
                           function(n, _, prevdepth)
                             return prepend_prevdepth(n, prevdepth)
                           end)
luatexbase.create_callback('pre_append_to_vlist_filter',
                           'list', false)
-- 
--
-- End of file `pre_append_to_vlist_filter.lua'.
