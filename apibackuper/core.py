#!/usr/bin/env python
# -*- coding: utf8 -*-
from pprint import pprint
import logging
import urllib3
import click

from .cmds.project import ProjectBuilder

urllib3.disable_warnings()

# logging.getLogger().addHandler(logging.StreamHandler())
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.DEBUG)


def enable_verbose():
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.DEBUG,
    )


@click.group()
def cli1():
    pass


@cli1.command()
@click.option("--config", "-c", default=None, help="Configuration file name")
@click.option("--pagekey",
              "-k",
              default=None,
              help="Page/iteration key for API")
@click.option("--pagesize", "-p", default=None, help="Page size for iteration")
@click.option(
    "--datakey",
    "-d",
    default=None,
    help="Data field with object items in API responses",
)
@click.option(
    "--itemkey",
    "-i",
    default=None,
    help=
    "Item unique key to identify unique items. Multiple keys separated with comma could be used too.",
)
@click.option("--changekey",
              "-e",
              default=None,
              help="Field to identify data change")
@click.option(
    "--iterateby",
    "-b",
    default="page",
    help="Way to iterate API. By 'page' or 'number'",
)
@click.option("--http-mode",
              "-m",
              default="GET",
              help="API mode: 'GET' or 'POST'")
@click.option(
    "--work-modes",
    "-u",
    default="full",
    help=
    "Download modes supported by this API, could be 'full', 'incremental' or 'update'. Multiple modes could be used",
)
@click.option("--verbose",
              "-v",
              count=False,
              help="Verbose output. Print additional info")
def init(
    url,
    pagekey,
    pagesize,
    datakey,
    itemkey,
    changekey,
    http_mode,
    iterateby,
    work_modes,
    verbose,
):
    """Initializes project with required parameters"""
    if verbose:
        enable_verbose()
    acmd = ProjectBuilder()
    acmd.init(
        url,
        pagekey,
        pagesize,
        datakey,
        itemkey,
        changekey,
        iterateby,
        http_mode,
        work_modes,
    )


@click.group()
def cli2():
    pass


@cli2.command()
@click.argument("name")
def create(name):
    """Creates new project"""
    ProjectBuilder.create(name)
    pass


@click.group()
def cli3():
    pass


@cli3.command()
@click.argument("mode", default="full")
@click.option("--projectpath", "-p", default=None, help="Project path")
@click.option("--verbose",
              "-v",
              count=False,
              help="Verbose output. Print additional info")
def run(mode, projectpath, verbose):
    """Executes project, collects data from API"""
    if verbose:
        enable_verbose()
    if projectpath:
        acmd = ProjectBuilder(projectpath)
    else:
        acmd = ProjectBuilder(projectpath)
    acmd.run(mode)


@click.group()
def cli4():
    pass


@cli4.command()
@click.argument("mode", default="full")
@click.option("--projectpath", "-p", default=None, help="Project path")
def estimate(mode, projectpath):
    """Estimate data size, records number and execution time"""
    if projectpath:
        acmd = ProjectBuilder(projectpath)
    else:
        acmd = ProjectBuilder(projectpath)
    acmd.estimate(mode)


@click.group()
def cli5():
    pass


@cli5.command()
@click.argument("format", default="jsonl")
@click.argument("filename", default=None)
@click.option("--projectpath", "-p", default=None, help="Project path")
@click.option("--verbose",
              "-v",
              count=False,
              help="Verbose output. Print additional info")
def export(format, filename, projectpath, verbose):
    """Exports data as jsonl, json, bson or csv file"""
    if verbose:
        enable_verbose()
    if projectpath:
        acmd = ProjectBuilder(projectpath)
    else:
        acmd = ProjectBuilder(projectpath)
    acmd.export(format, filename)
    pass


@click.group()
def cli6():
    pass


@cli6.command()
@click.option("--projectpath", "-p", default=None, help="Project path")
def info(projectpath):
    """Information about project like params and stats"""
    if projectpath:
        acmd = ProjectBuilder(projectpath)
    else:
        acmd = ProjectBuilder(projectpath)
    report = acmd.info(stats=True)
    pprint(report)


@click.group()
def cli7():
    pass


@cli7.command()
@click.argument("mode")
@click.option("--projectpath", "-p", default=None, help="Project path")
def follow(mode, projectpath):
    """Follow already extracted data to collect details. Use one of modes: full or continue"""
    if projectpath:
        acmd = ProjectBuilder(projectpath)
    else:
        acmd = ProjectBuilder(projectpath)
    acmd.follow(mode)


@click.group()
def cli8():
    pass


@cli8.command()
@click.option("--projectpath", "-p", default=None, help="Project path")
def getfiles(projectpath):
    """Download files associated with records"""
    if projectpath:
        acmd = ProjectBuilder(projectpath)
    else:
        acmd = ProjectBuilder(projectpath)
    acmd.getfiles()
    pass


@click.group()
def cli9():
    pass


@cli9.command()
@click.argument("filename", default=None)
@click.option("--projectpath", "-p", default=None, help="Project path")
def package(filename, projectpath):
    """Create frictionless package"""
    if projectpath:
        acmd = ProjectBuilder(projectpath)
    else:
        acmd = ProjectBuilder(projectpath)
    acmd.to_package(filename)


cli = click.CommandCollection(
    sources=[cli2, cli3, cli4, cli5, cli6, cli7, cli8, cli9])

# if __name__ == '__main__':
#    cli()
