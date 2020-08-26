#!/usr/bin/env python
# -*- coding: utf8 -*-
import click
import logging
from pprint import pprint

from .cmds.project import ProjectBuilder

#logging.getLogger().addHandler(logging.StreamHandler())
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG)

def enableVerbose():
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.DEBUG)


@click.group()
def cli1():
    pass

@cli1.command()
@click.option('--config', '-c', default=None, help="Configuration file name")
@click.option('--pagekey', '-k', default=None, help="Page/iteration key for API")
@click.option('--pagesize', '-p', default=None, help="Page size for iteration")
@click.option('--datakey', '-d', default=None, help="Data field with object items in API responses")
@click.option('--itemkey', '-i', default=None, help="Item unique key to identify unique items. Multiple keys separated with comma could be used too.")
@click.option('--changekey', '-e', default=None, help="Field to identify data change")
@click.option('--iterateby', '-b', default='page', help="Way to iterate API. By 'page' or 'number'")
@click.option('--http-mode', '-m', default='GET', help="API mode: 'GET' or 'POST'")
@click.option('--work-modes', '-u', default="full", help="Download modes supported by this API, could be 'full', 'incremental' or 'update'. Multiple modes could be used")
@click.option('--verbose', '-v', count=False, help='Verbose output. Print additional info')
def init(url, pagekey, pagesize, datakey, itemkey, changekey, http_mode, iterateby, work_modes, verbose):
    """Initializes project with required parameters"""
    if verbose:
        enableVerbose()
    acmd = ProjectBuilder()
    acmd.init(url, pagekey, pagesize, datakey, itemkey, changekey, iterateby, http_mode, work_modes)
    pass

@click.group()
def cli2():
    pass

@cli2.command()
@click.argument('name')
def create(name):
    """Creates new project"""
    ProjectBuilder.create(name)
    pass


@click.group()
def cli3():
    pass

@cli3.command()
@click.argument('mode', default="full")
@click.option('--projectpath', '-p', default=None, help='Project path')
@click.option('--verbose', '-v', count=False, help='Verbose output. Print additional info')
def run(mode, projectpath, verbose):
    """Executes project, collects data from API"""
    if verbose:
        enableVerbose()
    if projectpath:
        acmd = ProjectBuilder(projectpath)
    else:
        acmd = ProjectBuilder(projectpath)
    acmd.run(mode)
    pass


@click.group()
def cli4():
    pass

@cli4.command()
@click.argument('mode', default='full')
@click.option('--projectpath', '-p', default=None, help='Project path')
def estimate(mode, projectpath):
    """Estimate data size, records number and execution time"""
    if projectpath:
        acmd = ProjectBuilder(projectpath)
    else:
        acmd = ProjectBuilder(projectpath)
    acmd.estimate(mode)
    pass


@click.group()
def cli5():
    pass

@cli5.command()
@click.argument('format', default='jsonl')
@click.argument('filename', default=None)
@click.option('--projectpath', '-p', default=None, help='Project path')
@click.option('--verbose', '-v', count=False, help='Verbose output. Print additional info')
def export(format, filename, projectpath, verbose):
    """Exports data as jsonl, json, bson or csv file"""
    if verbose:
        enableVerbose()
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
@click.option('--projectpath', '-p', default=None, help='Project path')
def info(projectpath):
    """Information about project like params and stats"""
    if projectpath:
        acmd = ProjectBuilder(projectpath)
    else:
        acmd = ProjectBuilder(projectpath)
    report = acmd.info(stats=True)
    pprint(report)
    pass



cli = click.CommandCollection(sources=[ cli2, cli3, cli4, cli5, cli6])

#if __name__ == '__main__':
#    cli()

