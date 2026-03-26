--
-- Copyright (C) 2009-2016 John MacFarlane, Hans Hagen
--
-- Permission is hereby granted, free of charge, to any person obtaining
-- a copy of this software and associated documentation files (the
-- "Software"), to deal in the Software without restriction, including
-- without limitation the rights to use, copy, modify, merge, publish,
-- distribute, sublicense, and/or sell copies of the Software, and to
-- permit persons to whom the Software is furnished to do so, subject to
-- the following conditions:
--
-- The above copyright notice and this permission notice shall be
-- included in all copies or substantial portions of the Software.
--
-- THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
-- EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
-- MERCHANTABILITY, FITNESS FOR PARTICULAR PURPOSE AND NONINFRINGEMENT.
-- IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
-- CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
-- TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
-- SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
--
-- Copyright (C) 2016-2026 Vít Starý Novotný, Andrej Genčur
--
-- This work may be distributed and/or modified under the
-- conditions of the LaTeX Project Public License, either version 1.3
-- of this license or (at your option) any later version.
-- The latest version of this license is in
--
--     http://www.latex-project.org/lppl.txt
--
-- and version 1.3 or later is part of all distributions of LaTeX
-- version 2005/12/01 or later.
--
-- This work has the LPPL maintenance status `maintained'.
-- The Current Maintainer of this work is Vít Starý Novotný.
--
-- Send bug reports, requests for additions and questions
-- either to the GitHub issue tracker at
--
--     https://github.com/witiko/markdown/issues
--
-- or to the e-mail address <witiko@mail.muni.cz>.
--
-- MODIFICATION ADVICE:
--
-- If you want to customize this file, it is best to make a copy of
-- the source file(s) from which it was produced. Use a different
-- name for your copy(ies) and modify the copy(ies); this will ensure
-- that your modifications do not get overwritten when you install a
-- new release of the standard system. You should also ensure that
-- your modified source file does not generate any modified file with
-- the same name as a standard file.
--
-- You will also need to produce your own, suitably named, .ins file to
-- control the generation of files from your source file; this file
-- should contain your own preambles for the files it generates, not
-- those in the standard .ins files.
--
local metadata = {
    version   = "3.13.0-0-gdd212d58",
    comment   = "A module for the conversion from markdown "
             .. "to plain TeX",
    author    = "John MacFarlane, Hans Hagen, Vít Starý Novotný, "
             .. "Andrej Genčur",
    copyright = {"2009-2016 John MacFarlane, Hans Hagen",
                 "2016-2026 Vít Starý Novotný, Andrej Genčur"},
    license   = "LPPL 1.3c"
}

local md5 = require("md5")
local M = {metadata = metadata}
local defaultOptions = {}
local experimentalOptions = {}
setmetatable(experimentalOptions, { __index = function (_, key)
  return defaultOptions[key] end })
defaultOptions.eagerCache = true
defaultOptions.experimental = false
defaultOptions.singletonCache = true
defaultOptions.unicodeNormalization = true
defaultOptions.unicodeNormalizationForm = "nfc"
defaultOptions.cacheDir = "."
defaultOptions.contentBlocksLanguageMap = "markdown-languages.json"
defaultOptions.debugExtensionsFileName = "debug-extensions.json"
defaultOptions.frozenCacheFileName = "frozenCache.tex"
defaultOptions.autoIdentifiers = false
defaultOptions.blankBeforeBlockquote = false
defaultOptions.blankBeforeCodeFence = false
defaultOptions.blankBeforeDivFence = false
defaultOptions.blankBeforeHeading = false
defaultOptions.blankBeforeHtmlBlock = false
defaultOptions.blankBeforeList = false
defaultOptions.bracketedSpans = false
defaultOptions.breakableBlockquotes = true
defaultOptions.citationNbsps = true
defaultOptions.citations = false
defaultOptions.codeSpans = true
defaultOptions.contentBlocks = false
defaultOptions.contentLevel = "block"
defaultOptions.debugExtensions = false
defaultOptions.definitionLists = false
defaultOptions.ensureJekyllData = false
defaultOptions.expectJekyllData = false
defaultOptions.extensions = {}
defaultOptions.fancyLists = false
defaultOptions.fencedCode = true
defaultOptions.fencedCodeAttributes = false
defaultOptions.fencedDivs = false
defaultOptions.finalizeCache = false
defaultOptions.frozenCacheCounter = 0
defaultOptions.gfmAutoIdentifiers = false
defaultOptions.hashEnumerators = false
defaultOptions.headerAttributes = false
defaultOptions.html = true
defaultOptions.htmlOverLinks = false
experimentalOptions.htmlOverLinks = true
defaultOptions.hybrid = false
defaultOptions.inlineCodeAttributes = false
defaultOptions.inlineNotes = false
defaultOptions.jekyllData = false
defaultOptions.linkAttributes = false
defaultOptions.lineBlocks = false
defaultOptions.mark = false
defaultOptions.notes = false
defaultOptions.pipeTables = false
defaultOptions.preserveTabs = true
defaultOptions.rawAttribute = false
defaultOptions.relativeReferences = false
defaultOptions.shiftHeadings = 0
defaultOptions.slice = "^ $"
defaultOptions.smartEllipses = false
defaultOptions.startNumber = true
defaultOptions.strikeThrough = false
defaultOptions.stripIndent = false
defaultOptions.subscripts = false
defaultOptions.superscripts = false
defaultOptions.tableAttributes = false
defaultOptions.tableCaptions = false
defaultOptions.taskLists = false
defaultOptions.texComments = false
defaultOptions.texMathDollars = false
defaultOptions.texMathDoubleBackslash = false
defaultOptions.texMathSingleBackslash = false
defaultOptions.tightLists = true
defaultOptions.underscores = true
local util = {}
function util.cache(dir, string, salt, transform, suffix)
  local digest = md5.sumhexa(string .. (salt or ""))
  local name = util.pathname(dir, digest .. suffix)
  local file = io.open(name, "r")
  local result = nil
  if file == nil then -- If no cache entry exists, create a new one.
    file = assert(io.open(name, "w"),
      [[Could not open file "]] .. name .. [[" for writing]])
    result = string
    if transform ~= nil then
      result = transform(result)
    end
    assert(file:write(result))
    assert(file:close())
  end
  return name, result
end
function util.pathname(dir, file)
  if #dir == 0 then
    return file
  else
    return dir .. "/" .. file
  end
end
function util.salt(options)
  local opt_string = {}
  for k, _ in pairs(defaultOptions) do
    local v = options[k]
    if type(v) == "table" then
      for _, i in ipairs(v) do
        opt_string[#opt_string+1] = k .. "=" .. tostring(i)
      end
    elseif k ~= "cacheDir" then
      opt_string[#opt_string+1] = k .. "=" .. tostring(v)
    end
  end
  table.sort(opt_string)
  local salt = table.concat(opt_string, ",")
            .. "," .. metadata.version
  return salt
end
util.warning = (function()
  local function warning(s)
    io.stderr:write("Warning: " .. s .. "\n")
  end
  return warning
end)()
function M.new(options)
  options = options or {}
  setmetatable(options, { __index = function (_, key)
    return defaultOptions[key] end })
  if options.experimental then
    setmetatable(options, { __index = function (_, key)
      return experimentalOptions[key] end })
  end
  local parser_convert = nil
  return function(input, include_flat_output)
    local function convert(input)
      if parser_convert == nil then
        local parser = require("markdown-parser")
        if metadata.version ~= parser.metadata.version then
          warn("markdown.lua " .. metadata.version .. " used with " ..
               "markdown-parser.lua " .. parser.metadata.version .. ".")
        end
        parser_convert = parser.new(options)
      end
      return parser_convert(input)
    end
    local raw_output, flat_output
    if options.eagerCache or options.finalizeCache then
      local salt = util.salt(options)
      local name, result = util.cache(options.cacheDir, input, salt,
                                      convert, ".md.tex")
      raw_output = [[\input{]] .. name .. [[}\relax]]
      flat_output = function()
        if result == nil then
          local input_file = assert(io.open(name, "r"),
            [[Could not open file "]] .. name .. [[" for reading]])
          result = assert(input_file:read("*a"))
          assert(input_file:close())
        end
        return result
      end
    else
      raw_output = convert(input)
      flat_output = function()
        return raw_output
      end
    end
    if options.finalizeCache then
      local file, mode
      if options.frozenCacheCounter > 0 then
        mode = "a"
      else
        mode = "w"
      end
      file = assert(io.open(options.frozenCacheFileName, mode),
        [[Could not open file "]] .. options.frozenCacheFileName
        .. [[" for writing]])
      assert(file:write(
        [[\expandafter\global\expandafter\def\csname ]]
        .. [[markdownFrozenCache]] .. options.frozenCacheCounter
        .. [[\endcsname{]] .. raw_output .. [[}]] .. "\n"))
      assert(file:close())
    end
    if include_flat_output then
      return raw_output, flat_output
    else
      return raw_output
    end
  end
end
return M
