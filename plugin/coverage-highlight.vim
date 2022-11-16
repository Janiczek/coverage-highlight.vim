" File: coverage-highlight.vim
" Author: Marius Gedminas <marius@gedmin.as>
" Version: 3.5.1
" Last Modified: 2022-03-01
" Contributors: Louis Cochen <louis.cochen@protonmail.ch>

let g:elm_coverage_binary = get(g:, 'elm_coverage_binary', '')

if &encoding == 'utf-8'
  let g:coverage_sign = get(g:, 'coverage_sign', '↣')
else
  let g:coverage_sign = get(g:, 'coverage_sign', '>>')
endif

if g:coverage_sign == ''
  sign define NoCoverage linehl=NoCoverage
else
  execute 'sign define NoCoverage text=' . g:coverage_sign
        \ . ' texthl=NoCoverage linehl=NoCoverage'
endif

command! -bar HighlightCoverage call coverage_highlight#highlight_all()
command! -bar HighlightCoverageRedo call coverage_highlight#highlight_redo()
command! -bar HighlightCoverageOff call coverage_highlight#off()
command! -bar ToggleCoverage call coverage_highlight#toggle()

augroup CoverageHighlight
  autocmd!
  autocmd ColorScheme * call coverage_highlight#define_highlights()
augroup END
