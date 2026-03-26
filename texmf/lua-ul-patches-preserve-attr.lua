--
-- This is file `lua-ul-patches-preserve-attr.lua',
-- generated with the docstrip utility.
--
-- The original source files were:
--
-- lua-ul.dtx  (with options: `preserve-attr')
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
local getfont = font.getfont

local direct = node.direct

local getattr = direct.getattributelist
local getid = direct.getid
local getpenalty = direct.getpenalty
local getprev = direct.getprev
local getwidth = direct.getwidth

local setattr = direct.setattributelist
local setkern = direct.setkern

local insert_after = direct.insert_after
local is_glyph = direct.is_glyph
local newnode = direct.new
local todirect = direct.todirect
local tonode = direct.tonode

local glue_id = node.id'glue'
local kern_t = node.id'kern'
local penalty_id = node.id'penalty'

local italcorr_sub
for i, n in next, node.subtypes'kern' do
  if n == 'italiccorrection' then italcorr_sub = i break end
end
assert(italcorr_sub)

local nests = tex.nest

local funcid = luatexbase.new_luafunction'sw@slant'
token.set_lua('sw@slant', funcid, 'protected')
lua.get_functions_table()[funcid] = function()
  local nest = nests.top
  local tail, after = todirect(nest.tail), nil
  local id = getid(tail)
  if id == glue_id then
    if getwidth(tail) == 0 then return end
    tail, after = getprev(tail), tail
    id = getid(tail)
  end
  if id == penalty_id then
    if getpenalty(tail) == 0 then return end
    tail, after = getprev(tail), tail
  end
  local cid, fontid = is_glyph(tail)
  if not cid then return end
  local fontdir = getfont(fontid)
  local characters = fontdir and fontdir.characters
  local char = characters and characters[cid]
  local kern = newnode(kern_t, italcorr_sub)
  setkern(kern, char and char.italic or 0)
  setattr(kern, getattr(tail))
  insert_after(tail, tail, kern)
  if not after then nest.tail = tonode(kern) end
end
-- 
--
-- End of file `lua-ul-patches-preserve-attr.lua'.
