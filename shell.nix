{ pkgs ? import <nixpkgs> { } }:

pkgs.mkShell {
  packages = [
    pkgs.sqlitebrowser
    pkgs.python3
  ];
}
