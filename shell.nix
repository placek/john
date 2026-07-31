{ pkgs ? import <nixpkgs> { } }:

pkgs.mkShell {
  packages = [
    pkgs.sqlitebrowser
    pkgs.python3
    pkgs.typst        # make pdf → egzegeza.pdf
  ];
}
